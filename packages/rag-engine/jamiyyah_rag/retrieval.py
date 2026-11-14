"""Hybrid retrieval fusion utilities (Dense + BM25 via Reciprocal Rank Fusion)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class RankedItem:
    """A candidate chunk scored by a retrieval or reranking stage."""

    chunk_id: str
    score: float
    has_valid_provenance: bool = True


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Iterable[str]],
    k: int = 60,
) -> List[Tuple[str, float]]:
    """Combine multiple ranked chunk_id lists using Reciprocal Rank Fusion (RRF)."""
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
