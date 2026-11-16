from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jamiyyah_rag import (
    GroundingConfig,
    OpenAICompatClient,
    PgVectorStore,
    RagSettings,
    RankedItem,
    SqliteVectorStore,
    VectorRecord,
    evaluate_retrieval_gate,
    expand_query_with_llm,
    generate_strict_grounded_answer,
    index_jsonl_files,
    reciprocal_rank_fusion,
    validate_citations,
)
from jamiyyah_rag.openai_compat import OpenAICompatError, _is_retryable_http_error
from typing_extensions import Self


class _FakeCursor:
    def __init__(self, fetchall_rows: list[Any] | None = None, fetchone_row: Any = None) -> None:
        self.executed: list[tuple[str, Any]] = []
        self.executemany_calls: list[tuple[str, list[Any]]] = []
        self._fetchall = fetchall_rows or []
        self._fetchone = fetchone_row

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql.strip(), params))

    def executemany(self, sql: str, params_seq: Any) -> None:
        self.executemany_calls.append((sql.strip(), list(params_seq)))

    def fetchall(self) -> list[Any]:
        return list(self._fetchall)

    def fetchone(self) -> Any:
        return self._fetchone


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


class TestRagEngine(unittest.TestCase):
    def test_reciprocal_rank_fusion_merges_ranks(self) -> None:
        fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
        self.assertEqual(fused[0][0], "b")

    def test_quality_gate_abstains_below_threshold(self) -> None:
        res = evaluate_retrieval_gate(
            [RankedItem(chunk_id="c1", score=0.64, has_valid_provenance=True)],
            min_reranker_score=0.65,
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.accepted_chunks, [])

    def test_quality_gate_ignores_invalid_provenance(self) -> None:
        res = evaluate_retrieval_gate(
            [RankedItem(chunk_id="c1", score=0.95, has_valid_provenance=False)],
            min_reranker_score=0.65,
        )
        self.assertFalse(res.passed)

    def test_citation_validator_detects_fabricated_id(self) -> None:
        res = validate_citations(
            "Pendapat ini diriwayatkan [ID: valid_1] dan [ID: fake_99].",
            allowed_chunk_ids=["valid_1"],
        )
        self.assertFalse(res.valid)
        self.assertEqual(res.missing_ids, ["fake_99"])

    def test_config_loads_env_defaults_for_pgvector_and_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "DATABASE_URL=postgresql://u:p@localhost:5432/db\n"
                "EMBEDDING_MODEL=embeddinggemma-2:440m\n"
                "LLM_BASE_URL=https://openrouter.ai/api/v1\n"
                "LLM_API_KEY=sk-test-value\n",
                encoding="utf-8",
            )
            cfg = RagSettings.from_env(root)
            self.assertEqual(cfg.vector_backend, "pgvector")
            self.assertEqual(cfg.embedding_model, "embeddinggemma-2:440m")
            self.assertEqual(cfg.llm_base_url, "https://openrouter.ai/api/v1")
            self.assertTrue(cfg.has_llm_credentials)

    def test_pgvector_store_upsert_and_cosine_search_sql(self) -> None:
        cursor = _FakeCursor(fetchall_rows=[("taqrib_01", 0.912)])
        conn = _FakeConn(cursor)
        store = PgVectorStore(
            "postgresql://postgres:postgres@localhost:5432/jamiyyah",
            connect_fn=lambda _url: conn,
        )
        store.ensure_schema()
        self.assertTrue(conn.committed)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", cursor.executed[0][0])

        inserted = store.upsert_many([
            VectorRecord(
                chunk_id="taqrib_01",
                model="embeddinggemma-2:440m",
                content_hash="abc",
                source_category="kitab_turats",
                book_title="Matan Taqrib",
                verification_status="pending",
                vector=[3.0, 4.0],
            )
        ])
        self.assertEqual(inserted, 1)
        self.assertEqual(len(cursor.executemany_calls), 1)

        hits = store.search(
            [1.0, 0.0],
            model="embeddinggemma-2:440m",
            limit=5,
            category="kitab_turats",
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].chunk_id, "taqrib_01")
        self.assertAlmostEqual(hits[0].cosine, 0.912, places=3)
        sql, params = cursor.executed[-1]
        self.assertIn("embedding <=> %s", sql)
        self.assertIn("source_category = %s", sql)
        self.assertEqual(params[-1], 5)

    def test_openai_compat_embed_and_strict_llm_guardrails(self) -> None:
        def fake_transport(url: str, payload: dict[str, Any], headers: dict[str, str], _t: float):
            if url.endswith("/embeddings"):
                return {
                    "data": [
                        {"index": 1, "embedding": [0.0, 1.0]},
                        {"index": 0, "embedding": [1.0, 0.0]},
                    ]
                }
            if payload["messages"][0]["content"].startswith("Anda membantu ekspansi kueri"):
                return {
                    "choices": [{"message": {"content": '{"ar_terms": ["مياه", "قلتين"]}'}}]
                }
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Air mutlak suci mensucikan [ID: c_air_1].",
                        }
                    }
                ]
            }

        client = OpenAICompatClient(
            base_url="http://localhost:11434/v1",
            api_key="test",
            transport=fake_transport,
        )
        vecs = client.embed(["satu", "dua"], model="embeddinggemma-2:440m")
        self.assertEqual(vecs, [[1.0, 0.0], [0.0, 1.0]])

        ar_terms = expand_query_with_llm("hukum air dua qullah", client, model="gpt-4o-mini")
        self.assertEqual(ar_terms, ["مياه", "قلتين"])

        chunks = [
            {
                "chunk_id": "c_air_1",
                "hierarchy": ["Taqrib", "Thaharah"],
                "citation": {"full_reference": "Taqrib hlm. 1"},
                "content": {"arabic_raw": "الْمِيَاهُ", "indonesian": "Air ada tujuh macam."},
            }
        ]
        gen = generate_strict_grounded_answer(
            "Macam air?",
            chunks,
            client,
            model="gpt-4o-mini",
            config=GroundingConfig(),
        )
        self.assertEqual(gen.status, "answered")
        self.assertEqual(gen.cited_ids, ["c_air_1"])

    def test_layer3_rejects_fabricated_llm_citation(self) -> None:
        def bad_transport(_u: str, _p: dict[str, Any], _h: dict[str, str], _t: float):
            return {"choices": [{"message": {"content": "Hukumnya wajib [ID: fake_hallucinated]."}}]}

        client = OpenAICompatClient("https://api.example.com/v1", "k", transport=bad_transport)
        chunks = [
            {
                "chunk_id": "c_real",
                "hierarchy": ["Taqrib"],
                "citation": {"full_reference": "Taqrib"},
                "content": {"arabic_raw": "نص", "indonesian": "Teks"},
            }
        ]
        gen = generate_strict_grounded_answer("Apa hukum?", chunks, client, model="m")
        self.assertEqual(gen.status, "tawaqquf")
        self.assertIsNone(gen.answer)
        self.assertEqual(gen.missing_ids, ["fake_hallucinated"])

    def test_incremental_indexer_skips_unchanged_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "sample.jsonl"
            rec = {
                "chunk_id": "c1",
                "doc_id": "d1",
                "source_category": "kitab_turats",
                "hierarchy": ["Taqrib", "Thaharah"],
                "content": {"embedding_text": "Kategori: Kitab Turats | Air"},
                "metadata": {"verification_status": "pending"},
            }
            jsonl.write_text(json.dumps(rec) + "\n", encoding="utf-8")
            store = SqliteVectorStore(root / "vec.sqlite")
            embed_client = OpenAICompatClient(
                "http://localhost:11434/v1",
                transport=lambda _u, p, _h, _t: {
                    "data": [{"index": i, "embedding": [1.0, 0.0]} for i, _ in enumerate(p["input"])]
                },
            )
            snapshots = []
            st1 = index_jsonl_files(
                [jsonl],
                store=store,
                embed_client=embed_client,
                model="m",
                progress_callback=snapshots.append,
            )
            self.assertEqual(st1.embedded, 1)
            self.assertEqual(st1.skipped_unchanged, 0)
            self.assertTrue(snapshots)
            self.assertEqual(snapshots[-1].percent, 100.0)
            self.assertEqual(snapshots[-1].total, 1)
            st2 = index_jsonl_files([jsonl], store=store, embed_client=embed_client, model="m")
            self.assertEqual(st2.embedded, 0)
            self.assertEqual(st2.skipped_unchanged, 1)

    def test_pipelined_indexer_batches_and_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            cfg = RagSettings.from_env(root)
            self.assertEqual(cfg.embedding_batch_size, 64)
            self.assertEqual(cfg.embedding_concurrency, 2)

            jsonl = root / "multi.jsonl"
            lines = []
            for i in range(5):
                lines.append(
                    json.dumps(
                        {
                            "chunk_id": f"c_{i}",
                            "doc_id": "d1",
                            "source_category": "kitab_turats",
                            "hierarchy": ["Taqrib"],
                            "content": {"embedding_text": f"Teks {i}"},
                            "metadata": {"verification_status": "pending"},
                        }
                    )
                )
            jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

            batch_sizes: list[int] = []

            def fake_transport(_u: str, p: dict[str, Any], _h: dict[str, str], _t: float) -> dict[str, Any]:
                batch_sizes.append(len(p["input"]))
                return {
                    "data": [{"index": i, "embedding": [float(i + 1), 0.0]} for i, _ in enumerate(p["input"])]
                }

            store = SqliteVectorStore(root / "vec.sqlite")
            embed_client = OpenAICompatClient("http://localhost:11434/v1", transport=fake_transport)
            stats = index_jsonl_files(
                [jsonl],
                store=store,
                embed_client=embed_client,
                model="m",
                batch_size=2,
                concurrency=2,
            )
            self.assertEqual(stats.scanned, 5)
            self.assertEqual(stats.embedded, 5)
            self.assertEqual(sorted(batch_sizes), [1, 2, 2])

    def test_embed_bisects_batch_on_transient_error(self) -> None:
        calls: list[list[str]] = []

        def flaky_transport(
            _u: str, p: dict[str, Any], _h: dict[str, str], _t: float
        ) -> dict[str, Any]:
            inputs = list(p["input"])
            calls.append(inputs)
            if len(inputs) > 2:
                raise OpenAICompatError("HTTP 400: do embedding request: wsarecv: forcibly closed")
            return {
                "data": [
                    {"index": i, "embedding": [float(len(t)), 1.0]}
                    for i, t in enumerate(inputs)
                ]
            }

        client = OpenAICompatClient("http://localhost:11434/v1", transport=flaky_transport)
        vecs = client.embed(["a", "bb", "ccc", "dddd"], model="m")
        self.assertEqual(vecs, [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0], [4.0, 1.0]])
        self.assertEqual(calls, [["a", "bb", "ccc", "dddd"], ["a", "bb"], ["ccc", "dddd"]])

    def test_retryable_ollama_http_error_detection(self) -> None:
        self.assertTrue(_is_retryable_http_error(400, '{"error":{"message":"health resp: connection refused"}}'))
        self.assertTrue(_is_retryable_http_error(400, '{"error":{"message":"do embedding request: wsarecv: An existing connection was forcibly closed"}}'))
        self.assertTrue(_is_retryable_http_error(503, "unavailable"))
        self.assertFalse(_is_retryable_http_error(400, '{"error":{"message":"model not found"}}'))


if __name__ == "__main__":
    unittest.main()
