-- Jamiyyah Project: pgvector schema for canonical chunk dense embeddings
-- Usage:
--   createdb jamiyyah
--   psql "$DATABASE_URL" -f packages/rag-engine/sql/001_init_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_category TEXT NOT NULL,
    book_title TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    dim INTEGER NOT NULL,
    embedding vector NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model
    ON chunk_embeddings (model);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_filters
    ON chunk_embeddings (model, source_category, verification_status, book_title);

-- Opsional: setelah mengetahui dimensi model (misalnya 768 untuk embeddinggemma-2:440m),
-- Anda dapat menambahkan indeks HNSW berbasis ekspresi untuk pencarian skala besar:
-- CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_hnsw_768
--     ON chunk_embeddings USING hnsw ((embedding::vector(768)) vector_cosine_ops)
--     WHERE dim = 768;
