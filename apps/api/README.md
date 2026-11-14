# `@jamiyyah/api`

Backend API service (REST / tRPC) untuk Jamiyyah Project.

## Tanggung Jawab
- Menyediakan endpoint tanya-jawab dan penelusuran referensi berbasis RAG Engine (`packages/rag-engine`).
- Mengintegrasikan database PostgreSQL + pgvector/Qdrant serta sparse retrieval (BM25).
- Memvalidasi request/response dan citation payload menggunakan `@jamiyyah/schema`.
