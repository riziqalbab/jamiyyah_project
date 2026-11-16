"""Batch incremental vector indexer with live progress callbacks for Jamiyyah corpora."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
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


@dataclass(frozen=True)
class IndexProgress:
    """Incremental progress snapshot emitted during ``index_jsonl_files``."""

    total: int
    scanned: int
    embedded: int
    skipped_unchanged: int
    current_file: str
    percent: float


def _chunk_embedding_text(rec: dict[str, Any]) -> str:
    content = rec.get("content") or {}
    emb = (content.get("embedding_text") or "").strip()
    if emb:
        return emb
    hier = " > ".join(rec.get("hierarchy") or [])
    indo = (content.get("indonesian") or "").strip()
    ar = (content.get("arabic_clean") or content.get("arabic_raw") or "").strip()
    return f"Hierarki: {hier} | Konteks: {indo} | Ibarat: {ar}".strip()


def count_jsonl_records(
    jsonl_paths: Sequence[Path],
    *,
    max_chunks: int | None = None,
) -> int:
    """Count total non-empty JSONL lines across ``jsonl_paths`` for progress percentage."""
    total = 0
    for path in jsonl_paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    total += 1
                    if max_chunks is not None and total >= max_chunks:
                        return total
    return total


def index_jsonl_files(
    jsonl_paths: Sequence[Path],
    *,
    store: VectorStore,
    embed_client: OpenAICompatClient,
    model: str,
    batch_size: int = 64,
    concurrency: int = 2,
    max_chunks: int | None = None,
    progress_callback: Callable[[IndexProgress], None] | None = None,
) -> IndexStats:
    """Incrementally embed canonical JSONL chunks into ``store`` with pipelined batching."""
    batch_size = max(1, batch_size)
    concurrency = max(1, concurrency)
    max_in_flight = max(2, concurrency * 2)

    total = count_jsonl_records(jsonl_paths, max_chunks=max_chunks)
    existing = store.existing_hashes(model)
    scanned = 0
    embedded = 0
    skipped = 0
    current_file = ""

    def emit(force: bool = False) -> None:
        if progress_callback is None:
            return
        if not force and scanned % 200 != 0:
            return
        pct = round((scanned / total) * 100.0, 1) if total > 0 else 100.0
        progress_callback(
            IndexProgress(
                total=total,
                scanned=scanned,
                embedded=embedded,
                skipped_unchanged=skipped,
                current_file=current_file,
                percent=min(100.0, pct),
            )
        )

    pending: list[tuple[dict[str, Any], str, str]] = []
    in_flight: deque[tuple[list[tuple[dict[str, Any], str, str]], Future[list[list[float]]]]] = deque()

    def iter_records(path: Path) -> Iterable[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if raw:
                    yield json.loads(raw)

    def drain_one() -> None:
        nonlocal embedded
        batch_items, fut = in_flight.popleft()
        vectors = fut.result()
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
            for (rec, _text, chash), vec in zip(batch_items, vectors)
        ]
        embedded += store.upsert_many(records)
        emit(force=True)

    def submit_batch(executor: ThreadPoolExecutor) -> None:
        if not pending:
            return
        batch_items = list(pending)
        pending.clear()
        texts = [item[1] for item in batch_items]
        fut = executor.submit(embed_client.embed, texts, model=model)
        in_flight.append((batch_items, fut))
        if len(in_flight) >= max_in_flight:
            drain_one()

    emit(force=True)
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for path in jsonl_paths:
            if not path.is_file():
                continue
            current_file = path.name
            emit(force=True)
            for rec in iter_records(path):
                if max_chunks is not None and scanned >= max_chunks:
                    break
                scanned += 1
                text = _chunk_embedding_text(rec)
                chash = content_sha256(text)
                if existing.get(rec["chunk_id"]) == chash:
                    skipped += 1
                    emit(force=False)
                    continue
                pending.append((rec, text, chash))
                if len(pending) >= batch_size:
                    submit_batch(executor)
            if max_chunks is not None and scanned >= max_chunks:
                break

        submit_batch(executor)
        while in_flight:
            drain_one()

    emit(force=True)
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


def _render_cli_progress(progress: IndexProgress) -> None:
    width = 28
    filled = int((progress.percent / 100.0) * width) if progress.total > 0 else width
    bar = "█" * filled + "░" * (width - filled)
    msg = (
        f"\r[{bar}] {progress.percent:5.1f}% "
        f"({progress.scanned}/{progress.total}) "
        f"embedded={progress.embedded} skipped={progress.skipped_unchanged}"
    )
    if progress.current_file:
        msg += f" [{progress.current_file}]"
    sys.stdout.write(msg)
    sys.stdout.flush()


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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Embedding batch size (default: EMBEDDING_BATCH_SIZE or 64)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Concurrent embedding requests (default: EMBEDDING_CONCURRENCY or 2)",
    )
    parser.add_argument("--max-chunks", type=int, default=None, help="Optional cap for testing")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    settings = RagSettings.from_env(repo_root)
    batch_size = args.batch_size if args.batch_size is not None else settings.embedding_batch_size
    concurrency = args.concurrency if args.concurrency is not None else settings.embedding_concurrency
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
        f"@ {settings.embedding_base_url} -> backend={settings.vector_backend} "
        f"(batch_size={batch_size}, concurrency={concurrency})"
    )
    stats = index_jsonl_files(
        paths,
        store=store,
        embed_client=embed_client,
        model=settings.embedding_model,
        batch_size=batch_size,
        concurrency=concurrency,
        max_chunks=args.max_chunks,
        progress_callback=_render_cli_progress,
    )
    print()
    print(
        f"Done: scanned={stats.scanned}, newly_embedded={stats.embedded}, "
        f"skipped={stats.skipped_unchanged}, total_indexed={stats.total_in_store}"
    )


if __name__ == "__main__":
    main()
