"""Batch incremental vector indexer for Jamiyyah Canonical JSONL corpora."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jamiyyah_rag.config import RagSettings
from jamiyyah_rag.openai_compat import OpenAICompatClient
from jamiyyah_rag.pgvector_store import PgVectorStore, VectorStore
from jamiyyah_rag.vector_store import SqliteVectorStore, VectorRecord, content_sha256


def create_vector_store(settings: RagSettings) -> VectorStore:
    """Instantiate configured vector store backend (default: pgvector)."""
    if settings.vector_backend == "sqlite":
        return SqliteVectorStore(settings.vector_db_path)
    return PgVectorStore(
        database_url=settings.database_url,
        table_name=settings.pgvector_table,
    )


@dataclass(frozen=True)
class IndexStats:
    """Summary of an indexing pass."""

    scanned: int
    embedded: int
    skipped_unchanged: int
    total_in_store: int


def _chunk_embedding_text(rec: dict[str, Any]) -> str:
    content = rec.get("content") or {}
    emb = (content.get("embedding_text") or "").strip()
    if emb:
        return emb
    hier = " > ".join(rec.get("hierarchy") or [])
    indo = (content.get("indonesian") or "").strip()
    ar = (content.get("arabic_clean") or content.get("arabic_raw") or "").strip()
    return f"Hierarki: {hier} | Konteks: {indo} | Ibarat: {ar}".strip()


def index_jsonl_files(
    jsonl_paths: Sequence[Path],
    *,
    store: VectorStore,
    embed_client: OpenAICompatClient,
    model: str,
    batch_size: int = 16,
    max_chunks: int | None = None,
) -> IndexStats:
    """Incrementally embed canonical JSONL chunks into ``store``."""
    existing = store.existing_hashes(model)
    scanned = 0
    embedded = 0
    skipped = 0

    pending: list[tuple[dict[str, Any], str, str]] = []

    def flush_batch() -> None:
        nonlocal embedded
        if not pending:
            return
        texts = [item[1] for item in pending]
        vectors = embed_client.embed(texts, model=model)
        records = [
            VectorRecord(
                chunk_id=rec["chunk_id"],
                model=model,
                content_hash=chash,
                source_category=rec.get("source_category", "kitab_turats"),
                book_title=(rec.get("hierarchy") or [rec.get("doc_id", "Kitab")])[0],
                verification_status=(rec.get("metadata") or {}).get(
                    "verification_status", "pending"
                ),
                vector=vec,
            )
            for (rec, _text, chash), vec in zip(pending, vectors)
        ]
        embedded += store.upsert_many(records)
        pending.clear()

    def iter_records(path: Path) -> Iterable[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if raw:
                    yield json.loads(raw)

    for path in jsonl_paths:
        if not path.is_file():
            continue
        for rec in iter_records(path):
            if max_chunks is not None and scanned >= max_chunks:
                break
            scanned += 1
            text = _chunk_embedding_text(rec)
            chash = content_sha256(text)
            if existing.get(rec["chunk_id"]) == chash:
                skipped += 1
                continue
            pending.append((rec, text, chash))
            if len(pending) >= batch_size:
                flush_batch()
        if max_chunks is not None and scanned >= max_chunks:
            break

    flush_batch()
    return IndexStats(
        scanned=scanned,
        embedded=embedded,
        skipped_unchanged=skipped,
        total_in_store=store.count(model=model),
    )


def default_dataset_paths(repo_root: Path, include_hadith: bool = False) -> list[Path]:
    """Return standard parsed JSONL files ordered by priority."""
    paths = [
        repo_root / "datasets" / "samples" / "canonical_sample.jsonl",
        repo_root / "datasets" / "parsed" / "kitab_turats" / "taqrib.jsonl",
        repo_root / "datasets" / "parsed" / "kitab_turats" / "fathul_qarib.jsonl",
    ]
    if include_hadith:
        paths.append(repo_root / "datasets" / "parsed" / "hadist" / "hadits.jsonl")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Index Jamiyyah Canonical JSONL corpora into pgvector via Ollama embeddings."
    )
    parser.add_argument(
        "--include-hadith",
        action="store_true",
        help="Also index all 38k+ records from datasets/parsed/hadist/hadits.jsonl",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create pgvector extension & chunk_embeddings table before indexing",
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Embedding batch size")
    parser.add_argument("--max-chunks", type=int, default=None, help="Optional cap for testing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    settings = RagSettings.from_env(repo_root)
    store = create_vector_store(settings)
    if args.init_db and isinstance(store, PgVectorStore):
        store.ensure_schema()

    embed_client = OpenAICompatClient(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        timeout=60.0,
    )

    paths = default_dataset_paths(repo_root, include_hadith=args.include_hadith)
    print(
        f"Indexing {len(paths)} JSONL files using {settings.embedding_model} "
        f"@ {settings.embedding_base_url} -> backend={settings.vector_backend}"
    )
    stats = index_jsonl_files(
        paths,
        store=store,
        embed_client=embed_client,
        model=settings.embedding_model,
        batch_size=args.batch_size,
        max_chunks=args.max_chunks,
    )
    print(
        f"Done: scanned={stats.scanned}, newly_embedded={stats.embedded}, "
        f"skipped={stats.skipped_unchanged}, total_indexed={stats.total_in_store}"
    )


if __name__ == "__main__":
    main()
