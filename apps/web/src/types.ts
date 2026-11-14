import type { JamiyyahChunk } from "@jamiyyah/schema";

export type { JamiyyahChunk };

export interface PgVectorStatus {
  connected: boolean;
  schema_ready: boolean;
  count: number;
  error?: string;
}

export interface RagRuntimeInfo {
  vector_backend: string;
  pgvector: PgVectorStatus | null;
  embedding_model: string;
  embedding_base_url: string;
  indexed_vectors: number;
  llm_model: string;
  llm_base_url: string;
  llm_configured: boolean;
  min_reranker_score: number;
}

export interface HealthResponse {
  total_chunks: number;
  by_category: Record<string, number>;
  by_verification_status: Record<string, number>;
  by_book: Record<string, number>;
  loaded_files: string[];
  hadith_loading: boolean;
  hadith_loaded: boolean;
  rag?: RagRuntimeInfo;
}

export interface BookChapterItem {
  chunk_id: string;
  label: string;
  short_label: string;
  verification_status: string;
}

export interface BookChapter {
  title: string;
  chunk_count: number;
  items: BookChapterItem[];
}

export interface BookSummary {
  book_key: string;
  title: string;
  source_category: string;
  chunk_count: number;
  chapters: BookChapter[];
}

export interface QueryExpansion {
  id_terms: string[];
  ar_terms: string[];
  concepts: Array<{ id: string; ar: string[] }>;
}

export interface SearchHit {
  chunk: JamiyyahChunk;
  rrf_score: number;
  bm25_id: number;
  bm25_ar: number;
  dense_cosine?: number;
  rerank_score: number;
}

export interface SearchResponse {
  expansion: QueryExpansion;
  retrieval_mode?: string;
  hits: SearchHit[];
}

export interface AskResponse {
  status: "answered" | "tawaqquf";
  query: string;
  expansion: QueryExpansion;
  retrieval_mode?: string;
  rag_mode?: string;
  llm_model?: string;
  llm_error?: string | null;
  threshold: number;
  grounding_config: {
    temperature: number;
    require_citations: boolean;
    allow_external_knowledge: boolean;
  };
  layer1_gate: {
    passed: boolean;
    reason: string;
    accepted_count?: number;
    top_score: number;
  };
  layer3_validation: {
    valid: boolean;
    cited_ids: string[];
    missing_ids: string[];
  };
  answer: string | null;
  sources: SearchHit[];
}

export type ActiveTab = "chat" | "maktabah" | "inspector";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  category?: string;
  askResult?: AskResponse;
  error?: string;
}

export interface ChatThread {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}
