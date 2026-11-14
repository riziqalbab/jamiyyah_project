"""PostgreSQL + pgvector dense vector store for Jamiyyah RAG retrieval."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any, Protocol

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from jamiyyah_rag.vector_store import VectorHit, VectorRecord, l2_normalize

_SAFE_IDENT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _validate_identifier(name: str) -> str:
    if not name or not set(name).issubset(_SAFE_IDENT_CHARS) or name[0].isdigit():
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


class VectorStore(Protocol):
    """Common interface implemented by PgVectorStore and SqliteVectorStore."""

    def upsert_many(self, records: Iterable[VectorRecord]) -> int: ...

    def existing_hashes(self, model: str) -> dict[str, str]: ...

    def count(self, model: str | None = None) -> int: ...

    def search(
        self,
        query_vector: Sequence[float],
        *,
        model: str,
        limit: int = 40,
        category: str | None = None,
        book_title: str | None = None,
        verification_status: str | None = None,
    ) -> list[VectorHit]: ...


class PgVectorStore:
    """PostgreSQL + pgvector store supporting cosine similarity search and filtering."""

    def __init__(
        self,
        database_url: str,
        *,
        table_name: str = "chunk_embeddings",
        connect_fn: Callable[[str], Any] | None = None,
    ) -> None:
        self.database_url = database_url
        self.table_name = _validate_identifier(table_name)
        self._connect_fn = connect_fn

    def _connect(self) -> Any:
        if self._connect_fn is not None:
            return self._connect_fn(self.database_url)
        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    def ensure_schema(self) -> None:
        """Create the ``vector`` extension and embeddings table if missing."""
        ddl_ext = "CREATE EXTENSION IF NOT EXISTS vector"
        ddl_tbl = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                chunk_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_category TEXT NOT NULL,
                book_title TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                dim INTEGER NOT NULL,
                embedding vector NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """
        ddl_idx_model = (
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_model "
            f"ON {self.table_name} (model)"
        )
        ddl_idx_filters = (
            f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_filters "
            f"ON {self.table_name} (model, source_category, verification_status, book_title)"
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl_ext)
                cur.execute(ddl_tbl)
                cur.execute(ddl_idx_model)
                cur.execute(ddl_idx_filters)
            conn.commit()

    def upsert_many(self, records: Iterable[VectorRecord]) -> int:
        """Insert or update normalized embeddings inside PostgreSQL."""
        rows: list[tuple[Any, ...]] = []
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
                Vector(norm),
            ))
        if not rows:
            return 0

        sql = f"""
            INSERT INTO {self.table_name} (
                chunk_id, model, content_hash, source_category,
                book_title, verification_status, dim, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
                model = EXCLUDED.model,
                content_hash = EXCLUDED.content_hash,
                source_category = EXCLUDED.source_category,
                book_title = EXCLUDED.book_title,
                verification_status = EXCLUDED.verification_status,
                dim = EXCLUDED.dim,
                embedding = EXCLUDED.embedding,
                updated_at = NOW()
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()
        return len(rows)

    def existing_hashes(self, model: str) -> dict[str, str]:
        """Return ``{chunk_id: content_hash}`` stored in pgvector for ``model``."""
        sql = f"SELECT chunk_id, content_hash FROM {self.table_name} WHERE model = %s"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (model,))
            return {str(cid): str(chash) for cid, chash in cur.fetchall()}

    def count(self, model: str | None = None) -> int:
        """Return indexed vector count (or 0 if table/connection is unavailable)."""
        try:
            with self._connect() as conn, conn.cursor() as cur:
                if model:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE model = %s",
                        (model,),
                    )
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row = cur.fetchone()
                return int(row[0]) if row else 0
        except psycopg.Error:
            return 0

    def status(self, model: str | None = None) -> dict[str, Any]:
        """Return pgvector connectivity and vector count without leaking DATABASE_URL."""
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT to_regclass(%s)", (f"public.{self.table_name}",))
                reg = cur.fetchone()
                if not reg or reg[0] is None:
                    return {"connected": True, "schema_ready": False, "count": 0}
                if model:
                    cur.execute(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE model = %s",
                        (model,),
                    )
                else:
                    cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row = cur.fetchone()
                return {
                    "connected": True,
                    "schema_ready": True,
                    "count": int(row[0]) if row else 0,
                }
        except psycopg.Error as exc:
            return {
                "connected": False,
                "schema_ready": False,
                "count": 0,
                "error": str(exc).splitlines()[0],
            }

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
        """Query top-K nearest chunks using pgvector cosine distance ``<=>``."""
        norm_q = l2_normalize(query_vector)
        if not norm_q:
            return []
        q_vec = Vector(norm_q)

        clauses = ["model = %s", "dim = %s"]
        filter_params: list[Any] = [model, len(norm_q)]
        if category:
            clauses.append("source_category = %s")
            filter_params.append(category)
        if book_title:
            clauses.append("book_title = %s")
            filter_params.append(book_title)
        if verification_status:
            clauses.append("verification_status = %s")
            filter_params.append(verification_status)

        where_sql = " AND ".join(clauses)
        sql = f"""
            SELECT chunk_id, 1.0 - (embedding <=> %s) AS cosine
            FROM {self.table_name}
            WHERE {where_sql}
            ORDER BY embedding <=> %s
            LIMIT %s
        """
        params: list[Any] = [q_vec, *filter_params, q_vec, limit]
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return [
            VectorHit(chunk_id=str(cid), cosine=max(0.0, min(1.0, float(cos))))
            for cid, cos in rows
        ]
