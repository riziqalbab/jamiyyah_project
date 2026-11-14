# Jamiyyah Architecture

Dokumen ini merangkum arsitektur teknis **Jamiyyah Project** yang terdiri dari dua subsistem utama.

## 1. Data Ingestion & Standardization Pipeline

```text
Raw Sources (.csv, .bok/SQLite, HTML, PDF)
  -> Parser & Extractor (packages/parsers)
  -> Arabic Normalizer (packages/normalizer: arabic_raw + arabic_clean)
  -> Semantic & Structural Chunker
  -> Schema Validator (packages/schema: Pydantic / Zod -> .jsonl)
  -> Multilingual Embedding (BAAI/bge-m3) & Indexing (Dense + BM25)
```

## 2. Multi-Layered RAG Runtime

```text
User Query (Indonesian)
  -> Cross-Lingual Query Expansion (Indonesian -> Arabic Fiqh Terms)
  -> Hybrid Search (Dense Vector + Sparse BM25) + RRF Fusion
  -> Cross-Encoder Reranker (BAAI/bge-reranker-v2-m3)
  -> Layer 1: Retrieval Quality Gate (min_reranker_score >= 0.65, valid provenance)
  -> Layer 2: Strict Grounded Generation (temperature = 0.0, [ID: <chunk_id>])
  -> Layer 3: Citation & Claim Entailment Validation
```

## 3. Prinsip Guardrails

- **Abstention (*Tawaqquf*):** Jika Layer 1 gagal atau konteks tidak cukup, LLM tidak dipanggil dan sistem menolak menyimpulkan.
- **No Fabricated Citations:** Layer 3 memverifikasi seluruh `[ID: <chunk_id>]` terhadap database sumber sebelum jawaban ditampilkan.
