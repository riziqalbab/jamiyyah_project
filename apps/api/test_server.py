"""Tests for the Jamiyyah prototype API corpus index and 3-Layer RAG Q&A."""

from __future__ import annotations

import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from server import CorpusIndex, run_grounded_qa


def _build_fast_index() -> CorpusIndex:
    repo_root = Path(__file__).resolve().parents[2]
    idx = CorpusIndex(repo_root)
    idx.load_default_datasets(include_hadith=False)
    return idx


def test_corpus_health_and_books() -> None:
    idx = _build_fast_index()
    stats = idx.stats()
    assert stats["total_chunks"] >= 378
    assert "kitab_turats" in stats["by_category"]
    books = idx.list_books()
    titles = {b["title"] for b in books}
    assert "Matan al-Ghayah wat-Taqrib" in titles
    assert "Fathul Qarib al-Mujib" in titles


def test_bilingual_search_taqrib_and_sample() -> None:
    idx = _build_fast_index()
    res = idx.search("macam air dua qullah", limit=5)
    assert res["hits"], "Expected search hits for macam air dua qullah"
    assert res["expansion"]["ar_terms"], "Expected cross-lingual Arabic terms"
    top_chunk = res["hits"][0]["chunk"]
    assert top_chunk["content"]["arabic_raw"]


def test_grounded_qa_answers_with_valid_citations() -> None:
    idx = _build_fast_index()
    queries = [
        "Apa saja macam air yang sah untuk bersuci dan ukuran dua qullah?",
        "Apa saja rukun shalat menurut Matan Taqrib?",
        "Bagaimana syarat akad salam dan batasannya?",
        "Hukum transaksi paylater dan riba",
    ]
    for query in queries:
        res = run_grounded_qa(idx, query=query, min_score=0.65)
        assert res["status"] == "answered", f"Expected answered for {query!r}, got {res}"
        assert res["layer1_gate"]["passed"] is True
        assert res["layer3_validation"]["valid"] is True
        assert res["layer3_validation"]["cited_ids"]
        assert res["answer"] is not None


def test_out_of_domain_triggers_tawaqquf() -> None:
    idx = _build_fast_index()
    res = run_grounded_qa(
        idx,
        query="Bagaimana prediksi harga saham teknologi dan kripto besok?",
        min_score=0.65,
    )
    assert res["status"] == "tawaqquf"
    assert res["layer1_gate"]["passed"] is False
    assert res["answer"] is None
