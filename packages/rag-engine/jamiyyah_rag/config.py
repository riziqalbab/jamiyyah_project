"""Environment and runtime configuration for the Jamiyyah RAG engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(env_path: Path) -> dict[str, str]:
    """Parse a simple ``.env`` file without external dependencies.

    Values already set in ``os.environ`` are never overwritten unless the caller
    merges them explicitly. Keys and values are kept strictly in memory.
    """
    parsed: dict[str, str] = {}
    if not env_path.is_file():
        return parsed
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            parsed[key] = value
    return parsed


@dataclass(frozen=True)
class RagSettings:
    """Configuration for pgvector, OpenAI-compatible Ollama embeddings, and cloud LLM."""

    database_url: str = "postgresql://postgres:postgres@localhost:5432/jamiyyah"
    vector_backend: str = "pgvector"
    pgvector_table: str = "chunk_embeddings"
    embedding_base_url: str = "http://localhost:11434/v1"
    embedding_model: str = "embeddinggemma-2:440m"
    embedding_api_key: str = "ollama"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    min_reranker_score: float = 0.65
    vector_db_path: Path = Path("qdrant_storage/vectors.sqlite")
    request_timeout_sec: float = 30.0

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.llm_api_key.strip() and self.llm_base_url.strip())

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> RagSettings:
        """Load settings from process environment overlaid on ``<repo_root>/.env``."""
        root = repo_root or Path.cwd()
        file_env = load_env_file(root / ".env")

        def get(name: str, default: str) -> str:
            val = os.environ.get(name)
            if val is not None and val != "":
                return val
            return file_env.get(name, default)

        raw_db = get("VECTOR_DB_PATH", "qdrant_storage/vectors.sqlite")
        db_path = Path(raw_db)
        if not db_path.is_absolute():
            db_path = root / db_path

        try:
            min_score = float(get("RERANKER_MIN_SCORE", "0.65"))
        except ValueError:
            min_score = 0.65

        return cls(
            database_url=get(
                "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/jamiyyah"
            ),
            vector_backend=get("VECTOR_BACKEND", "pgvector").lower(),
            pgvector_table=get("PGVECTOR_TABLE", "chunk_embeddings"),
            embedding_base_url=get("EMBEDDING_BASE_URL", "http://localhost:11434/v1").rstrip("/"),
            embedding_model=get("EMBEDDING_MODEL", "embeddinggemma-2:440m"),
            embedding_api_key=get("EMBEDDING_API_KEY", "ollama"),
            llm_base_url=get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            llm_model=get("LLM_MODEL", "gpt-4o-mini"),
            llm_api_key=get("LLM_API_KEY", ""),
            min_reranker_score=min_score,
            vector_db_path=db_path,
        )
