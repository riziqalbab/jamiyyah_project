"""Persistent SQLite-backed dense vector store with fast cosine similarity search."""

from __future__ import annotations

import hashlib
import math
import sqlite3
import threading
from array import array
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return L2-normalized copy of ``vector`` (or zeros if norm is zero)."""
    sq = sum(x * x for x in vector)
    if sq <= 0.0:
        return [0.0 for _ in vector]
    inv = 1.0 / math.sqrt(sq)
    return [x * inv for x in vector]


def content_sha256(text: str) -> str:
    """Compute stable SHA-256 digest for incremental re-indexing checks."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pack_floats(vec: Sequence[float]) -> bytes:
    buf = array("f", vec)
    return buf.tobytes()


def _unpack_floats(blob: bytes) -> array[float]:
    buf = array("f")
    buf.frombytes(blob)
    return buf


@dataclass(frozen=True)
class VectorRecord:
    """Dense embedding entry persisted for a single canonical chunk."""

    chunk_id: str
    model: str
    content_hash: str
    source_category: str
    book_title: str
    verification_status: str
    vector: Sequence[float]


@dataclass(frozen=True)
class VectorHit:
    """A dense retrieval candidate ordered by cosine similarity."""

    chunk_id: str
    cosine: float


class SqliteVectorStore:
    """Lightweight persistent dense vector store using SQLite + float32 blobs."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cache_model: str | None = None
        self._cache: list[tuple[str, str, str, str, array[float]]] = []
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), timeout=30.0)

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_vectors (
                    chunk_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_category TEXT NOT NULL,
                    book_title TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    norm_vector BLOB NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_vectors_model ON chunk_vectors(model)"
            )

    def upsert_many(self, records: Iterable[VectorRecord]) -> int:
        """Insert or update normalized embeddings and invalidate in-RAM cache."""
        rows: list[tuple[str, str, str, str, str, str, int, bytes]] = []
        for rec in records:
            norm = l2_normalize(rec.vector)
            rows.append((
                rec.chunk_id,
                rec.model,
                rec.content_hash,
                rec.source_category,
                rec.book_title,
                rec.verification_status,
                len(norm),
                _pack_floats(norm),
            ))
        if not rows:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO chunk_vectors (
                    chunk_id, model, content_hash, source_category,
                    book_title, verification_status, dim, norm_vector
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    model = excluded.model,
                    content_hash = excluded.content_hash,
                    source_category = excluded.source_category,
                    book_title = excluded.book_title,
                    verification_status = excluded.verification_status,
                    dim = excluded.dim,
                    norm_vector = excluded.norm_vector
                """,
                rows,
            )
            self._cache_model = None
            self._cache = []
        return len(rows)

    def existing_hashes(self, model: str) -> dict[str, str]:
        """Return ``{chunk_id: content_hash}`` already stored for ``model``."""
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT chunk_id, content_hash FROM chunk_vectors WHERE model = ?",
                (model,),
            )
            return {cid: chash for cid, chash in cur.fetchall()}

    def count(self, model: str | None = None) -> int:
        """Count indexed chunks (optionally filtered by embedding model)."""
        with self._lock, self._connect() as conn:
            if model:
                row = conn.execute(
                    "SELECT COUNT(*) FROM chunk_vectors WHERE model = ?",
                    (model,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()
            return int(row[0]) if row else 0

    def _ensure_cache(self, model: str) -> list[tuple[str, str, str, str, array[float]]]:
        with self._lock:
            if self._cache_model == model and self._cache:
                return self._cache
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT chunk_id, source_category, book_title, verification_status, norm_vector
                    FROM chunk_vectors
                    WHERE model = ?
                    """,
                    (model,),
                )
                loaded = [
                    (cid, cat, book, verif, _unpack_floats(blob))
                    for cid, cat, book, verif, blob in cur.fetchall()
                ]
            self._cache_model = model
            self._cache = loaded
            return self._cache

    def search(
        self,
        query_vector: Sequence[float],
        *,
        model: str,
        limit: int = 40,
        category: str | None = None,
        book_title: str | None = None,
        verification_status: str | None = None,
    ) -> list[VectorHit]:
        """Return top-K chunks by cosine similarity against ``query_vector``."""
        norm_q = l2_normalize(query_vector)
        q_dim = len(norm_q)
        if q_dim == 0:
            return []

        entries = self._ensure_cache(model)
        scored: list[VectorHit] = []
        for cid, cat, book, verif, vec in entries:
            if category and cat != category:
                continue
            if book_title and book != book_title:
                continue
            if verification_status and verif != verification_status:
                continue
            if len(vec) != q_dim:
                continue
            dot = math.fsum(a * b for a, b in zip(norm_q, vec))
            scored.append(VectorHit(chunk_id=cid, cosine=max(0.0, min(1.0, dot))))

        scored.sort(key=lambda item: item.cosine, reverse=True)
        return scored[:limit]
