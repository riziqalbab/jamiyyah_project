"""RAG Engine components: Hybrid Retrieval (pgvector + BM25), Ollama/Cloud LLM, and Guardrails."""

from jamiyyah_rag.config import RagSettings, load_env_file
from jamiyyah_rag.guardrails import (
    CitationValidationResult,
    GroundingConfig,
    QualityGateResult,
    evaluate_retrieval_gate,
    extract_citation_ids,
    validate_citations,
)
from jamiyyah_rag.indexer import (
    IndexProgress,
    IndexStats,
    create_vector_store,
    default_dataset_paths,
    index_jsonl_files,
)
from jamiyyah_rag.openai_compat import OpenAICompatClient, OpenAICompatError
from jamiyyah_rag.pgvector_store import PgVectorStore, VectorStore
from jamiyyah_rag.pipeline import (
    GroundedGenerationResult,
    build_rag_context,
    contextualize_and_expand_query,
    contextualize_query_fallback,
    expand_query_with_llm,
    generate_conversational_reply,
    generate_strict_grounded_answer,
    is_casual_conversation,
    normalize_chat_history,
)
from jamiyyah_rag.retrieval import RankedItem, reciprocal_rank_fusion
from jamiyyah_rag.vector_store import SqliteVectorStore, VectorHit, VectorRecord

__all__ = [
    "CitationValidationResult",
    "GroundedGenerationResult",
    "GroundingConfig",
    "IndexProgress",
    "IndexStats",
    "OpenAICompatClient",
    "OpenAICompatError",
    "PgVectorStore",
    "QualityGateResult",
    "RagSettings",
    "RankedItem",
    "SqliteVectorStore",
    "VectorHit",
    "VectorRecord",
    "VectorStore",
    "build_rag_context",
    "contextualize_and_expand_query",
    "contextualize_query_fallback",
    "create_vector_store",
    "default_dataset_paths",
    "evaluate_retrieval_gate",
    "expand_query_with_llm",
    "extract_citation_ids",
    "generate_conversational_reply",
    "generate_strict_grounded_answer",
    "index_jsonl_files",
    "is_casual_conversation",
    "load_env_file",
    "normalize_chat_history",
    "reciprocal_rank_fusion",
    "validate_citations",
]
