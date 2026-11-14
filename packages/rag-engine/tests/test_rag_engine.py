import unittest

from jamiyyah_rag import (
    RankedItem,
    evaluate_retrieval_gate,
    reciprocal_rank_fusion,
    validate_citations,
)


class TestRagEngine(unittest.TestCase):
    def test_reciprocal_rank_fusion_merges_ranks(self) -> None:
        fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
        self.assertEqual(fused[0][0], "b")

    def test_quality_gate_abstains_below_threshold(self) -> None:
        res = evaluate_retrieval_gate(
            [RankedItem(chunk_id="c1", score=0.64, has_valid_provenance=True)],
            min_reranker_score=0.65,
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.accepted_chunks, [])

    def test_quality_gate_ignores_invalid_provenance(self) -> None:
        res = evaluate_retrieval_gate(
            [RankedItem(chunk_id="c1", score=0.95, has_valid_provenance=False)],
            min_reranker_score=0.65,
        )
        self.assertFalse(res.passed)

    def test_citation_validator_detects_fabricated_id(self) -> None:
        res = validate_citations(
            "Pendapat ini diriwayatkan [ID: valid_1] dan [ID: fake_99].",
            allowed_chunk_ids=["valid_1"],
        )
        self.assertFalse(res.valid)
        self.assertEqual(res.missing_ids, ["fake_99"])


if __name__ == "__main__":
    unittest.main()
