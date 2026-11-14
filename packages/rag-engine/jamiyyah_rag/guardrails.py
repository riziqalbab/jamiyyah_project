"""Three-Layer Guardrails: Retrieval Quality Gate, Grounding Config, Citation Validator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Set

from jamiyyah_rag.retrieval import RankedItem

_CITATION_TAG_RE = re.compile(r"\[ID:\s*([^\]]+?)\s*\]")


@dataclass(frozen=True)
class GroundingConfig:
    """Layer 2 strict grounded generation defaults."""

    temperature: float = 0.0
    require_citations: bool = True
    allow_external_knowledge: bool = False


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of Layer 1 Retrieval Quality Gate."""

    passed: bool
    reason: str
    accepted_chunks: List[RankedItem]


@dataclass(frozen=True)
class CitationValidationResult:
    """Outcome of Layer 3 Citation Validation."""

    valid: bool
    cited_ids: List[str]
    missing_ids: List[str]


def evaluate_retrieval_gate(
    candidates: Sequence[RankedItem],
    min_reranker_score: float = 0.65,
) -> QualityGateResult:
    """Layer 1 Gate: abstain (tawaqquf) if no valid chunk meets the reranker threshold."""
    accepted = [
        item
        for item in candidates
        if item.has_valid_provenance and item.score >= min_reranker_score
    ]
    if not accepted:
        return QualityGateResult(
            passed=False,
            reason="Tawaqquf: no chunk with valid provenance met the reranker threshold.",
            accepted_chunks=[],
        )
    return QualityGateResult(passed=True, reason="OK", accepted_chunks=accepted)


def extract_citation_ids(answer_text: str) -> List[str]:
    """Extract all ``[ID: <chunk_id>]`` references from generated output."""
    return [match.group(1).strip() for match in _CITATION_TAG_RE.finditer(answer_text)]


def validate_citations(
    answer_text: str,
    allowed_chunk_ids: Iterable[str],
    require_at_least_one: bool = True,
) -> CitationValidationResult:
    """Layer 3 Validator: verify all cited IDs exist in the retrieved context set."""
    allowed: Set[str] = set(allowed_chunk_ids)
    cited = extract_citation_ids(answer_text)
    missing = [cid for cid in cited if cid not in allowed]

    if require_at_least_one and not cited:
        return CitationValidationResult(valid=False, cited_ids=[], missing_ids=[])

    return CitationValidationResult(
        valid=len(missing) == 0,
        cited_ids=cited,
        missing_ids=missing,
    )
