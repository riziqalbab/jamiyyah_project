"""Tests for the Jamiyyah prototype API corpus index and 3-Layer RAG Q&A."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from jamiyyah_rag import OpenAICompatClient, RagSettings, SqliteVectorStore, index_jsonl_files
from server import CorpusIndex, run_grounded_qa


def _build_fast_index(tmp_path: Path) -> CorpusIndex:
    repo_root = Path(__file__).resolve().parents[2]
    settings = RagSettings(
        vector_backend="sqlite",
        vector_db_path=tmp_path / "empty.sqlite",
        llm_api_key="",
    )
    idx = CorpusIndex(repo_root, settings=settings)
    idx.load_default_datasets(include_hadith=False)
    return idx


def test_corpus_health_and_books(tmp_path: Path) -> None:
    idx = _build_fast_index(tmp_path)
    stats = idx.stats()
    assert stats["total_chunks"] >= 378
    assert "kitab_turats" in stats["by_category"]
    assert "rag" in stats
    books = idx.list_books()
    titles = {b["title"] for b in books}
    assert "Matan al-Ghayah wat-Taqrib" in titles
    assert "Fathul Qarib al-Mujib" in titles


def test_bilingual_search_taqrib_and_sample(tmp_path: Path) -> None:
    idx = _build_fast_index(tmp_path)
    res = idx.search("macam air dua qullah", limit=5)
    assert res["hits"], "Expected search hits for macam air dua qullah"
    assert res["expansion"]["ar_terms"], "Expected cross-lingual Arabic terms"
    top_chunk = res["hits"][0]["chunk"]
    assert top_chunk["content"]["arabic_raw"]


def test_grounded_qa_answers_with_valid_citations(tmp_path: Path) -> None:
    idx = _build_fast_index(tmp_path)
    queries = [
        "Apa saja macam air yang sah untuk bersuci dan ukuran dua qullah?",
        "Apa saja rukun shalat menurut Matan Taqrib?",
        "Bagaimana syarat akad salam dan batasannya?",
        "Hukum transaksi paylater dan riba",
    ]
    for query in queries:
        res = run_grounded_qa(idx, query=query, min_score=0.65)
        assert res["status"] == "answered", f"Expected answered for {query!r}, got {res}"
        assert res["layer1_gate"]["passed"] is True
        assert res["layer3_validation"]["valid"] is True
        assert res["layer3_validation"]["cited_ids"]
        assert res["answer"] is not None


def test_out_of_domain_triggers_tawaqquf_without_calling_llm() -> None:
    llm_calls = 0

    def fail_if_called(_u: str, payload: dict[str, Any], _h: dict[str, str], _t: float):
        nonlocal llm_calls
        if not payload["messages"][0]["content"].startswith("Anda membantu ekspansi kueri"):
            llm_calls += 1
        return {"choices": [{"message": {"content": '{"ar_terms": []}'}}]}

    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
        settings = RagSettings(vector_backend="sqlite", vector_db_path=Path(tmp) / "v.sqlite")
        llm_client = OpenAICompatClient("https://api.example.com/v1", "k", transport=fail_if_called)
        idx = CorpusIndex(repo_root, settings=settings, llm_client=llm_client)
        idx.load_default_datasets(include_hadith=False)
        res = run_grounded_qa(
            idx,
            query="Bagaimana prediksi harga saham teknologi dan kripto besok?",
            min_score=0.65,
        )
        assert res["status"] == "tawaqquf"
        assert res["layer1_gate"]["passed"] is False
        assert res["answer"] is None
        assert llm_calls == 0


def test_hybrid_dense_and_cloud_llm_grounded_qa() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sample_jsonl = repo_root / "datasets" / "samples" / "canonical_sample.jsonl"

    def fake_embed(_u: str, payload: dict[str, Any], _h: dict[str, str], _t: float):
        return {
            "data": [{"index": i, "embedding": [1.0, 0.0, 0.0]} for i, _ in enumerate(payload["input"])]
        }

    def fake_llm(_u: str, payload: dict[str, Any], _h: dict[str, str], _t: float):
        sys_msg = payload["messages"][0]["content"]
        if sys_msg.startswith("Anda membantu ekspansi kueri"):
            return {"choices": [{"message": {"content": '{"ar_terms": ["قرض", "ربا"]}'}}]}
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Transaksi yang menarik manfaat dari pinjaman termasuk riba "
                            "[ID: bm_pwnu_jatim_2023_012_c01]."
                        )
                    }
                }
            ]
        }

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteVectorStore(Path(tmp) / "vec.sqlite")
        embed_client = OpenAICompatClient("http://localhost:11434/v1", transport=fake_embed)
        llm_client = OpenAICompatClient("https://api.openai.com/v1", "sk-x", transport=fake_llm)
        index_jsonl_files([sample_jsonl], store=store, embed_client=embed_client, model="embeddinggemma-2:440m")

        settings = RagSettings(
            vector_backend="sqlite",
            embedding_model="embeddinggemma-2:440m",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-x",
        )
        idx = CorpusIndex(
            repo_root,
            settings=settings,
            embed_client=embed_client,
            llm_client=llm_client,
            vector_store=store,
        )
        idx.load_default_datasets(include_hadith=False)
        res = run_grounded_qa(idx, query="Hukum transaksi paylater dan riba", min_score=0.65)
        assert res["status"] == "answered"
        assert res["retrieval_mode"] == "hybrid_dense_bm25"
        assert res["rag_mode"] == "llm_grounded"
        assert "bm_pwnu_jatim_2023_012_c01" in res["layer3_validation"]["cited_ids"]


def test_async_vector_indexing_job_progress(tmp_path: Path) -> None:
    import time

    repo_root = Path(__file__).resolve().parents[2]
    store = SqliteVectorStore(tmp_path / "async.sqlite")
    embed_client = OpenAICompatClient(
        "http://localhost:11434/v1",
        transport=lambda _u, p, _h, _t: {
            "data": [{"index": i, "embedding": [1.0, 0.0]} for i, _ in enumerate(p["input"])]
        },
    )
    settings = RagSettings(
        vector_backend="sqlite",
        embedding_model="embeddinggemma-2:440m",
        llm_api_key="",
    )
    idx = CorpusIndex(
        repo_root,
        settings=settings,
        embed_client=embed_client,
        vector_store=store,
    )
    job = idx.start_vector_indexing(include_hadith=False)
    assert job["state"] in {"running", "done"}

    deadline = time.time() + 10.0
    while time.time() < deadline:
        status = idx.get_index_job_status()
        if not status["running"]:
            break
        time.sleep(0.05)

    final_status = idx.get_index_job_status()
    assert final_status["state"] == "done"
    assert final_status["percent"] == 100.0
    assert final_status["total_in_store"] >= 378
