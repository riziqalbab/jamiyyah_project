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
    expand_query_with_llm,
    generate_strict_grounded_answer,
)
from jamiyyah_rag.retrieval import RankedItem, reciprocal_rank_fusion
from jamiyyah_rag.vector_store import SqliteVectorStore, VectorHit, VectorRecord

__all__ = [
    "CitationValidationResult",
    "GroundedGenerationResult",
    "GroundingConfig",
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
    "create_vector_store",
    "default_dataset_paths",
    "evaluate_retrieval_gate",
    "expand_query_with_llm",
    "extract_citation_ids",
    "generate_strict_grounded_answer",
    "index_jsonl_files",
    "load_env_file",
    "reciprocal_rank_fusion",
    "validate_citations",
]
