"""Lightweight local prototype API + static server for Jamiyyah Project."""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import re
import threading
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import psycopg
from jamiyyah_normalizer import normalize_arabic
from jamiyyah_rag.config import RagSettings
from jamiyyah_rag.guardrails import (
    GroundingConfig,
    evaluate_retrieval_gate,
    validate_citations,
)
from jamiyyah_rag.indexer import (
    create_vector_store,
    default_dataset_paths,
    index_jsonl_files,
)
from jamiyyah_rag.openai_compat import OpenAICompatClient, OpenAICompatError
from jamiyyah_rag.pgvector_store import PgVectorStore, VectorStore
from jamiyyah_rag.pipeline import expand_query_with_llm, generate_strict_grounded_answer
from jamiyyah_rag.retrieval import RankedItem, reciprocal_rank_fusion

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEB_SRC_DIR = _REPO_ROOT / "apps" / "web"
_WEB_DIST_DIR = _WEB_SRC_DIR / "dist"


def _resolve_web_dir() -> Path:
    if (_WEB_DIST_DIR / "index.html").is_file():
        return _WEB_DIST_DIR
    return _WEB_SRC_DIR

_TOKEN_RE = re.compile(r"[a-z0-9']+|[\u0600-\u06FF]+")

_STOPWORDS_ID = frozenset({
    "apa", "apakah", "bagaimana", "bagai", "siapa", "kapan", "dimana", "mengapa",
    "kenapa", "berapa", "mana", "yang", "dan", "atau", "di", "ke", "dari", "pada",
    "untuk", "dengan", "dalam", "itu", "ini", "adalah", "ialah", "yaitu", "yakni",
    "jika", "bila", "apabila", "kalau", "maka", "karena", "oleh", "sebagai",
    "tentang", "mengenai", "menurut", "hukum", "hukumnya", "syarat", "cara",
    "saja", "ada", "tidak", "bukan", "boleh", "wajib", "sunnah", "haram", "sah",
    "bisa", "dapat", "harus", "agar", "supaya", "telah", "sudah", "akan", "lagi",
    "saya", "aku", "kita", "kami", "mereka", "nya", "tersebut", "satu", "dua",
})

# Cross-lingual Indonesian -> Arabic fiqh & hadith query expansion table
_CROSS_LINGUAL_TERMS: dict[str, list[str]] = {
    "air": ["ماء", "مياه", "تطهير"],
    "bersuci": ["طهارة", "تطهير"],
    "suci": ["طهارة", "طاهر", "مطهر"],
    "qullah": ["قلتين", "قلة"],
    "kulit": ["جلود", "جلد", "دباغ"],
    "samak": ["دباغ", "بدباغ"],
    "bangkai": ["ميتة"],
    "siwak": ["سواك"],
    "wudhu": ["وضوء", "الوضوء"],
    "wudlu": ["وضوء", "الوضوء"],
    "istinja": ["استنجاء"],
    "mandi": ["غسل", "اغتسال"],
    "junub": ["جنابة", "غسل"],
    "khuf": ["خفين"],
    "tayammum": ["تيمم", "تراب"],
    "tayamum": ["تيمم", "تراب"],
    "najis": ["نجاسة", "نجس"],
    "haid": ["حيض"],
    "nifas": ["نفاس"],
    "shalat": ["صلاة", "الصلاة"],
    "sholat": ["صلاة", "الصلاة"],
    "solat": ["صلاة", "الصلاة"],
    "rukun": ["اركان", "فروض"],
    "sujud": ["سجود", "السهو"],
    "sahwi": ["سهو", "السهو"],
    "jamaah": ["جماعة"],
    "qashar": ["قصر", "مسافر"],
    "jamak": ["جمع", "مسافر"],
    "jumat": ["جمعة", "الجمعة"],
    "gerhana": ["كسوف", "خسوف"],
    "hujan": ["استسقاء"],
    "jenazah": ["جنائز", "ميت", "كفن"],
    "zakat": ["زكاة", "نصاب"],
    "fitrah": ["فطر", "زكاة"],
    "puasa": ["صيام", "صوم", "رمضان"],
    "itikaf": ["اعتكاف"],
    "haji": ["حج", "احرام", "طواف", "عرفة"],
    "umrah": ["عمرة", "حج"],
    "jual": ["بيع", "بيوع"],
    "beli": ["بيع", "بيوع"],
    "riba": ["ربا", "الربا"],
    "khiyar": ["خيار"],
    "salam": ["سلم", "السلم"],
    "gadai": ["رهن", "الرهن"],
    "wakaf": ["وقف", "الوقف"],
    "hibah": ["هبة"],
    "waris": ["فرائض", "ميراث", "عصبات"],
    "wasiat": ["وصية", "وصايا"],
    "nikah": ["نكاح", "النكاح", "ولي"],
    "wali": ["ولي", "نكاح"],
    "mahar": ["صداق", "مهر"],
    "talak": ["طلاق", "رجعة"],
    "cerai": ["طلاق", "خلع"],
    "iddah": ["عدة"],
    "nafkah": ["نفقة"],
    "jinayat": ["جنايات", "قتل", "قصاص", "دية"],
    "qishash": ["قصاص", "قود"],
    "zina": ["زنا", "محصن", "حد"],
    "jihad": ["جهاد", "جزية"],
    "kurban": ["اضحية", "ضحايا"],
    "aqiqah": ["عقيقة"],
    "akikah": ["عقيقة"],
    "sumpah": ["ايمان", "يمين"],
    "nadzar": ["نذر", "ايمان"],
    "paylater": ["قرض", "ربا", "منفعة"],
    "pinjaman": ["قرض", "عارية"],
    "utang": ["دين", "حوالة", "ضمان"],
    "hutang": ["دين", "حوالة", "ضمان"],
    "hadits": ["حدثنا", "قال", "رسول"],
    "niat": ["نية", "النية", "الاعمال"],
}


@dataclass(frozen=True)
class ChunkPointer:
    """Lightweight disk pointer + summary metadata for a JSONL chunk."""

    idx: int
    chunk_id: str
    doc_id: str
    source_category: str
    language: str
    hierarchy: tuple[str, ...]
    verification_status: str
    short_label: str
    file_path: Path
    offset: int
    length: int
    id_len: int
    ar_len: int
    book_key: str
    book_title: str


class CorpusIndex:
    """In-memory hybrid BM25 + pgvector Dense Vector index over Canonical JSONL datasets."""

    def __init__(
        self,
        repo_root: Path,
        *,
        settings: RagSettings | None = None,
        embed_client: OpenAICompatClient | None = None,
        llm_client: OpenAICompatClient | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.settings = settings or RagSettings.from_env(repo_root)
        self.vector_store = vector_store or create_vector_store(self.settings)
        self.embed_client = embed_client or OpenAICompatClient(
            base_url=self.settings.embedding_base_url,
            api_key=self.settings.embedding_api_key,
            timeout=self.settings.request_timeout_sec,
        )
        self.llm_client = llm_client or (
            OpenAICompatClient(
                base_url=self.settings.llm_base_url,
                api_key=self.settings.llm_api_key,
                timeout=self.settings.request_timeout_sec,
            )
            if self.settings.has_llm_credentials
            else None
        )
        self._lock = threading.RLock()
        self.pointers: list[ChunkPointer] = []
        self.id_to_idx: dict[str, int] = {}
        self.id_postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.ar_postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.id_total_len = 0
        self.ar_total_len = 0
        self.loaded_files: list[str] = []
        self.hadith_loading = False
        self.hadith_loaded = False

    def _tokenize_id(self, text: str) -> list[str]:
        tokens = _TOKEN_RE.findall(text.lower())
        return [t for t in tokens if len(t) > 1 and not _has_ar_char(t)]

    def _tokenize_ar(self, text: str) -> list[str]:
        clean = normalize_arabic(text)
        return [t for t in _TOKEN_RE.findall(clean) if _has_ar_char(t)]

    def load_jsonl_file(self, path: Path) -> int:
        if not path.exists():
            return 0
        rel_path = str(path.relative_to(self.repo_root))
        added = 0
        local_ptrs: list[ChunkPointer] = []
        local_id_postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        local_ar_postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        local_id_len = 0
        local_ar_len = 0

        with self._lock:
            base_idx = len(self.pointers)

        with path.open("rb") as handle:
            while True:
                offset = handle.tell()
                raw_line = handle.readline()
                if not raw_line:
                    break
                length = len(raw_line)
                stripped = raw_line.strip()
                if not stripped:
                    continue
                rec = json.loads(stripped.decode("utf-8"))
                idx = base_idx + added
                hierarchy = tuple(rec.get("hierarchy", ()))
                source_cat = rec.get("source_category", "kitab_turats")
                meta = rec.get("metadata", {})
                content = rec.get("content", {})
                citation = rec.get("citation", {})

                if source_cat == "hadith":
                    book_title = hierarchy[0] if hierarchy else "Hadits"
                    book_key = f"hadith:{book_title}"
                else:
                    book_title = hierarchy[0] if hierarchy else rec.get("doc_id", "Dokumen")
                    book_key = f"{source_cat}:{book_title}"

                id_text = " ".join([*hierarchy, content.get("indonesian", "")])
                id_tokens = self._tokenize_id(id_text)
                ar_tokens = self._tokenize_ar(content.get("arabic_clean") or content.get("arabic_raw", ""))

                for term, tf in Counter(id_tokens).items():
                    local_id_postings[term].append((idx, tf))
                for term, tf in Counter(ar_tokens).items():
                    local_ar_postings[term].append((idx, tf))

                local_id_len += len(id_tokens)
                local_ar_len += len(ar_tokens)
                local_ptrs.append(
                    ChunkPointer(
                        idx=idx,
                        chunk_id=rec["chunk_id"],
                        doc_id=rec["doc_id"],
                        source_category=source_cat,
                        language=rec.get("language", "mixed"),
                        hierarchy=hierarchy,
                        verification_status=meta.get("verification_status", "pending"),
                        short_label=citation.get("short_label", rec["chunk_id"]),
                        file_path=path,
                        offset=offset,
                        length=length,
                        id_len=max(len(id_tokens), 1),
                        ar_len=max(len(ar_tokens), 1),
                        book_key=book_key,
                        book_title=book_title,
                    )
                )
                added += 1

        with self._lock:
            for ptr in local_ptrs:
                self.pointers.append(ptr)
                self.id_to_idx[ptr.chunk_id] = ptr.idx
            for term, plist in local_id_postings.items():
                self.id_postings[term].extend(plist)
            for term, plist in local_ar_postings.items():
                self.ar_postings[term].extend(plist)
            self.id_total_len += local_id_len
            self.ar_total_len += local_ar_len
            self.loaded_files.append(rel_path)

        return added

    def load_default_datasets(self, include_hadith: bool = True) -> None:
        fast_paths = [
            self.repo_root / "datasets" / "samples" / "canonical_sample.jsonl",
            self.repo_root / "datasets" / "parsed" / "kitab_turats" / "taqrib.jsonl",
            self.repo_root / "datasets" / "parsed" / "kitab_turats" / "fathul_qarib.jsonl",
        ]
        for path in fast_paths:
            self.load_jsonl_file(path)

        hadith_path = self.repo_root / "datasets" / "parsed" / "hadist" / "hadits.jsonl"
        if include_hadith and hadith_path.exists():
            self.hadith_loading = True

            def _bg() -> None:
                try:
                    self.load_jsonl_file(hadith_path)
                    self.hadith_loaded = True
                finally:
                    self.hadith_loading = False

            threading.Thread(target=_bg, daemon=True).start()

    def read_record(self, chunk_id: str) -> dict[str, Any] | None:
        with self._lock:
            idx = self.id_to_idx.get(chunk_id)
            if idx is None:
                return None
            ptr = self.pointers[idx]
        with ptr.file_path.open("rb") as handle:
            handle.seek(ptr.offset)
            raw = handle.read(ptr.length)
        return json.loads(raw.decode("utf-8"))

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_cat = Counter(p.source_category for p in self.pointers)
            by_status = Counter(p.verification_status for p in self.pointers)
            by_book = Counter(p.book_title for p in self.pointers)
            vec_count = self.vector_store.count(model=self.settings.embedding_model)
            pg_status = (
                self.vector_store.status(model=self.settings.embedding_model)
                if isinstance(self.vector_store, PgVectorStore)
                else None
            )
            return {
                "total_chunks": len(self.pointers),
                "by_category": dict(by_cat),
                "by_verification_status": dict(by_status),
                "by_book": dict(by_book.most_common(20)),
                "loaded_files": list(self.loaded_files),
                "hadith_loading": self.hadith_loading,
                "hadith_loaded": self.hadith_loaded,
                "rag": {
                    "vector_backend": self.settings.vector_backend,
                    "pgvector": pg_status,
                    "embedding_model": self.settings.embedding_model,
                    "embedding_base_url": self.settings.embedding_base_url,
                    "indexed_vectors": vec_count,
                    "llm_model": self.settings.llm_model,
                    "llm_base_url": self.settings.llm_base_url,
                    "llm_configured": self.llm_client is not None,
                    "min_reranker_score": self.settings.min_reranker_score,
                },
            }

    def list_books(self) -> list[dict[str, Any]]:
        with self._lock:
            ptrs = list(self.pointers)
        books: dict[str, dict[str, Any]] = {}
        for ptr in ptrs:
            entry = books.get(ptr.book_key)
            if entry is None:
                entry = {
                    "book_key": ptr.book_key,
                    "title": ptr.book_title,
                    "source_category": ptr.source_category,
                    "chunk_count": 0,
                    "chapters": {},
                }
                books[ptr.book_key] = entry
            entry["chunk_count"] += 1
            if ptr.source_category == "hadith":
                chap_name = "Koleksi Hadits"
            else:
                chap_name = ptr.hierarchy[1] if len(ptr.hierarchy) > 1 else "Umum"
            chap = entry["chapters"].get(chap_name)
            if chap is None:
                chap = {"title": chap_name, "chunk_count": 0, "items": []}
                entry["chapters"][chap_name] = chap
            chap["chunk_count"] += 1
            if len(chap["items"]) < 80:
                chap["items"].append({
                    "chunk_id": ptr.chunk_id,
                    "label": ptr.hierarchy[-1] if ptr.hierarchy else ptr.chunk_id,
                    "short_label": ptr.short_label,
                    "verification_status": ptr.verification_status,
                })

        result = []
        for entry in books.values():
            result.append({
                "book_key": entry["book_key"],
                "title": entry["title"],
                "source_category": entry["source_category"],
                "chunk_count": entry["chunk_count"],
                "chapters": list(entry["chapters"].values()),
            })
        return result

    def expand_query(self, query: str) -> dict[str, Any]:
        id_tokens = [t for t in self._tokenize_id(query) if t not in _STOPWORDS_ID]
        if not id_tokens:
            id_tokens = self._tokenize_id(query)
        raw_ar_tokens = self._tokenize_ar(query)

        expanded_ar: list[str] = list(raw_ar_tokens)
        matched_concepts: list[dict[str, Any]] = []
        for tok in id_tokens:
            ar_terms = _CROSS_LINGUAL_TERMS.get(tok)
            if ar_terms:
                norm_terms = [normalize_arabic(t) for t in ar_terms]
                expanded_ar.extend(norm_terms)
                matched_concepts.append({"id": tok, "ar": ar_terms})

        # Deduplicate preserving order
        seen_ar: set[str] = set()
        unique_ar: list[str] = []
        for term in expanded_ar:
            if term and term not in seen_ar:
                seen_ar.add(term)
                unique_ar.append(term)

        return {
            "id_terms": list(dict.fromkeys(id_tokens)),
            "ar_terms": unique_ar,
            "concepts": matched_concepts,
        }

    def _bm25_scores(
        self,
        terms: list[str],
        postings: dict[str, list[tuple[int, int]]],
        is_arabic: bool,
        allowed_idxs: set[int] | None,
    ) -> dict[int, float]:
        with self._lock:
            n_docs = max(len(self.pointers), 1)
            avg_len = max((self.ar_total_len if is_arabic else self.id_total_len) / n_docs, 1.0)
            ptrs = self.pointers

        scores: dict[int, float] = defaultdict(float)
        k1 = 1.5
        b = 0.75
        for term in terms:
            plist = postings.get(term)
            if not plist:
                continue
            df = len(plist)
            idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for idx, tf in plist:
                if allowed_idxs is not None and idx not in allowed_idxs:
                    continue
                dl = ptrs[idx].ar_len if is_arabic else ptrs[idx].id_len
                denom = tf + k1 * (1.0 - b + b * (dl / avg_len))
                scores[idx] += idf * ((tf * (k1 + 1.0)) / denom)
        return scores

    def search(
        self,
        query: str,
        category: str | None = None,
        book_title: str | None = None,
        verification_status: str | None = None,
        limit: int = 12,
        extra_ar_terms: list[str] | None = None,
    ) -> dict[str, Any]:
        expansion = self.expand_query(query)
        id_terms = expansion["id_terms"]
        ar_terms = list(expansion["ar_terms"])
        if extra_ar_terms:
            seen_ar = set(ar_terms)
            for term in extra_ar_terms:
                norm_t = normalize_arabic(term)
                if norm_t and norm_t not in seen_ar:
                    seen_ar.add(norm_t)
                    ar_terms.append(norm_t)
            expansion["ar_terms"] = ar_terms

        with self._lock:
            allowed: set[int] | None = None
            if category or book_title or verification_status:
                allowed = {
                    p.idx
                    for p in self.pointers
                    if (not category or p.source_category == category)
                    and (not book_title or p.book_title == book_title)
                    and (not verification_status or p.verification_status == verification_status)
                }

        id_scores = self._bm25_scores(id_terms, self.id_postings, is_arabic=False, allowed_idxs=allowed)
        ar_scores = self._bm25_scores(ar_terms, self.ar_postings, is_arabic=True, allowed_idxs=allowed)

        id_ranked_idx = sorted(id_scores, key=id_scores.__getitem__, reverse=True)[:80]
        ar_ranked_idx = sorted(ar_scores, key=ar_scores.__getitem__, reverse=True)[:80]

        with self._lock:
            id_cids = [self.pointers[i].chunk_id for i in id_ranked_idx]
            ar_cids = [self.pointers[i].chunk_id for i in ar_ranked_idx]

        # Dense Vector Retrieval (Ollama OpenAI-compatible embeddings)
        dense_cids: list[str] = []
        dense_scores: dict[str, float] = {}
        retrieval_mode = "bm25_index_empty"
        vec_count = self.vector_store.count(model=self.settings.embedding_model)
        if vec_count > 0:
            try:
                q_vecs = self.embed_client.embed([query], model=self.settings.embedding_model)
                if q_vecs:
                    vec_hits = self.vector_store.search(
                        q_vecs[0],
                        model=self.settings.embedding_model,
                        limit=60,
                        category=category,
                        book_title=book_title,
                        verification_status=verification_status,
                    )
                    dense_cids = [vh.chunk_id for vh in vec_hits if vh.chunk_id in self.id_to_idx]
                    dense_scores = {vh.chunk_id: vh.cosine for vh in vec_hits}
                    retrieval_mode = "hybrid_dense_bm25"
            except OpenAICompatError as exc:
                retrieval_mode = f"bm25_fallback ({exc})"

        ranked_lists = [id_cids, ar_cids]
        if dense_cids:
            ranked_lists.append(dense_cids)

        fused = reciprocal_rank_fusion(ranked_lists, k=60)
        if not fused:
            return {"expansion": expansion, "retrieval_mode": retrieval_mode, "hits": []}

        # Compute calibrated relevance score in [0, 1] per candidate
        top_bm25_id = max(id_scores.values(), default=0.0)
        top_bm25_ar = max(ar_scores.values(), default=0.0)
        hits: list[dict[str, Any]] = []
        for chunk_id, rrf_score in fused[:limit]:
            rec = self.read_record(chunk_id)
            if rec is None:
                continue
            idx = self.id_to_idx[chunk_id]
            bm_id = id_scores.get(idx, 0.0)
            bm_ar = ar_scores.get(idx, 0.0)
            dense_cos = dense_scores.get(chunk_id, 0.0)

            rec_id_tokens = set(
                self._tokenize_id(" ".join([*rec.get("hierarchy", []), rec["content"].get("indonesian", "")]))
            )
            rec_ar_tokens = set(self._tokenize_ar(rec["content"].get("arabic_clean", "")))
            id_cov = (
                sum(1 for t in id_terms if t in rec_id_tokens) / max(len(id_terms), 1)
                if id_terms
                else 0.0
            )
            ar_cov = (
                sum(1 for t in ar_terms if t in rec_ar_tokens) / max(len(ar_terms), 1)
                if ar_terms
                else 0.0
            )
            norm_id = (bm_id / top_bm25_id) if top_bm25_id > 0 else 0.0
            norm_ar = (bm_ar / top_bm25_ar) if top_bm25_ar > 0 else 0.0

            lexical_score = (
                0.42 * max(id_cov, ar_cov)
                + 0.25 * (0.5 * id_cov + 0.5 * ar_cov)
                + 0.33 * max(norm_id, norm_ar)
            )
            if dense_cids:
                blended = 0.55 * dense_cos + 0.45 * lexical_score
                rerank_score = min(0.98, round(max(lexical_score, blended), 3))
            else:
                rerank_score = min(0.98, round(lexical_score, 3))

            matched_id_cnt = sum(1 for t in id_terms if t in rec_id_tokens)
            matched_ar_cnt = sum(1 for t in ar_terms if t in rec_ar_tokens)
            if (
                len(id_terms) >= 2
                and matched_id_cnt == 0
                and matched_ar_cnt == 0
                and dense_cos < 0.58
            ):
                rerank_score = 0.0
            elif (
                len(id_terms) >= 3
                and matched_id_cnt <= 1
                and matched_ar_cnt == 0
                and dense_cos < 0.62
            ):
                rerank_score = min(rerank_score, 0.42)

            hits.append({
                "chunk": rec,
                "rrf_score": round(rrf_score, 5),
                "bm25_id": round(bm_id, 3),
                "bm25_ar": round(bm_ar, 3),
                "dense_cosine": round(dense_cos, 4),
                "rerank_score": rerank_score,
            })

        hits.sort(key=lambda h: (h["rerank_score"], h["rrf_score"]), reverse=True)
        return {"expansion": expansion, "retrieval_mode": retrieval_mode, "hits": hits}


def _has_ar_char(text: str) -> bool:
    return any(0x0600 <= ord(ch) <= 0x06FF for ch in text)


def _snippet(text: str, max_len: int = 340) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_len:
        return clean
    cut = clean[:max_len].rsplit(" ", 1)[0]
    return f"{cut}..."


def _extractive_grounded_answer(accepted_hits: list[dict[str, Any]]) -> str:
    """Deterministic fallback answer compiled strictly from accepted chunks."""
    lines: list[str] = []
    primary = accepted_hits[0]["chunk"]
    primary_hier = " > ".join(primary.get("hierarchy", []))
    lines.append(
        f"Berdasarkan rujukan yang terverifikasi pada corpus lokal, pembahasan yang relevan "
        f"ditemukan dalam **{primary_hier}** [ID: {primary['chunk_id']}]:"
    )
    lines.append("")
    for hit in accepted_hits:
        ch = hit["chunk"]
        cid = ch["chunk_id"]
        label = " > ".join(ch.get("hierarchy", [])[:3])
        indo = _snippet(ch["content"].get("indonesian") or "", 320)
        if indo:
            lines.append(f"- **{label}:** {indo} [ID: {cid}]")
        else:
            ar_snip = _snippet(ch["content"].get("arabic_raw", ""), 200)
            lines.append(f"- **{label}:** {ar_snip} [ID: {cid}]")

    lines.append("")
    lines.append(
        "> *Catatan:* Ringkasan di atas disusun dalam mode ekstraktif (*strict grounding*) "
        "dari potongan kitab/hadits yang lolos ambang batas relevansi."
    )
    return "\n".join(lines)


def run_grounded_qa(
    corpus: CorpusIndex,
    query: str,
    min_score: float = 0.65,
    category: str | None = None,
) -> dict[str, Any]:
    """Execute the 3-Layer RAG Guardrails pipeline over local parsed corpora."""
    extra_ar_terms: list[str] = []
    if corpus.llm_client is not None:
        extra_ar_terms = expand_query_with_llm(
            query,
            corpus.llm_client,
            model=corpus.settings.llm_model,
        )

    search_res = corpus.search(
        query=query,
        category=category,
        limit=6,
        extra_ar_terms=extra_ar_terms,
    )
    hits = search_res["hits"]
    retrieval_mode = search_res.get("retrieval_mode", "bm25_index_empty")

    candidates = [
        RankedItem(
            chunk_id=h["chunk"]["chunk_id"],
            score=h["rerank_score"],
            has_valid_provenance=bool(
                h["chunk"].get("citation", {}).get("full_reference")
                and h["chunk"].get("content", {}).get("arabic_raw")
            ),
        )
        for h in hits
    ]

    gate = evaluate_retrieval_gate(candidates, min_reranker_score=min_score)
    grounding_cfg = GroundingConfig()

    if not gate.passed:
        return {
            "status": "tawaqquf",
            "query": query,
            "expansion": search_res["expansion"],
            "retrieval_mode": retrieval_mode,
            "rag_mode": "tawaqquf_gate",
            "threshold": min_score,
            "grounding_config": {
                "temperature": grounding_cfg.temperature,
                "require_citations": grounding_cfg.require_citations,
                "allow_external_knowledge": grounding_cfg.allow_external_knowledge,
            },
            "layer1_gate": {
                "passed": False,
                "reason": gate.reason,
                "top_score": hits[0]["rerank_score"] if hits else 0.0,
            },
            "layer3_validation": {
                "valid": True,
                "cited_ids": [],
                "missing_ids": [],
            },
            "answer": None,
            "sources": hits[:3],
        }

    accepted_ids = {item.chunk_id for item in gate.accepted_chunks}
    accepted_hits = [h for h in hits if h["chunk"]["chunk_id"] in accepted_ids][:4]
    accepted_chunks = [h["chunk"] for h in accepted_hits]

    rag_mode = "extractive_fallback"
    llm_error: str | None = None

    if corpus.llm_client is not None:
        try:
            gen = generate_strict_grounded_answer(
                query,
                accepted_chunks,
                corpus.llm_client,
                model=corpus.settings.llm_model,
                config=grounding_cfg,
            )
            rag_mode = "llm_grounded"
            return {
                "status": gen.status,
                "query": query,
                "expansion": search_res["expansion"],
                "retrieval_mode": retrieval_mode,
                "rag_mode": rag_mode,
                "llm_model": corpus.settings.llm_model,
                "threshold": min_score,
                "grounding_config": {
                    "temperature": grounding_cfg.temperature,
                    "require_citations": grounding_cfg.require_citations,
                    "allow_external_knowledge": grounding_cfg.allow_external_knowledge,
                },
                "layer1_gate": {
                    "passed": True,
                    "reason": gate.reason,
                    "accepted_count": len(accepted_hits),
                    "top_score": accepted_hits[0]["rerank_score"],
                },
                "layer3_validation": {
                    "valid": gen.status == "answered",
                    "reason": gen.reason,
                    "cited_ids": gen.cited_ids,
                    "missing_ids": gen.missing_ids,
                },
                "answer": gen.answer,
                "sources": accepted_hits,
            }
        except OpenAICompatError as exc:
            llm_error = str(exc)
            rag_mode = "extractive_fallback_llm_error"

    answer_text = _extractive_grounded_answer(accepted_hits)
    cit_check = validate_citations(
        answer_text,
        allowed_chunk_ids=accepted_ids,
        require_at_least_one=True,
    )

    return {
        "status": "answered" if cit_check.valid else "tawaqquf",
        "query": query,
        "expansion": search_res["expansion"],
        "retrieval_mode": retrieval_mode,
        "rag_mode": rag_mode,
        "llm_error": llm_error,
        "threshold": min_score,
        "grounding_config": {
            "temperature": grounding_cfg.temperature,
            "require_citations": grounding_cfg.require_citations,
            "allow_external_knowledge": grounding_cfg.allow_external_knowledge,
        },
        "layer1_gate": {
            "passed": True,
            "reason": gate.reason,
            "accepted_count": len(accepted_hits),
            "top_score": accepted_hits[0]["rerank_score"],
        },
        "layer3_validation": {
            "valid": cit_check.valid,
            "cited_ids": cit_check.cited_ids,
            "missing_ids": cit_check.missing_ids,
        },
        "answer": answer_text if cit_check.valid else None,
        "sources": accepted_hits,
    }


def make_handler(corpus: CorpusIndex, web_dir: Path) -> type[BaseHTTPRequestHandler]:
    """Build HTTP request handler bound to ``corpus`` and static ``web_dir``."""

    class JamiyyahHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, rel_path: str) -> None:
            clean = rel_path.lstrip("/") or "index.html"
            target = (web_dir / clean).resolve()
            if not str(target).startswith(str(web_dir.resolve())) or not target.is_file():
                target = web_dir / "index.html"
            data = target.read_bytes()
            ctype, _ = mimetypes.guess_type(str(target))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{ctype or 'application/octet-stream'}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                self._send_json(corpus.stats())
                return

            if path == "/api/books":
                self._send_json({"books": corpus.list_books()})
                return

            if path.startswith("/api/chunk/"):
                chunk_id = urllib.parse.unquote(path[len("/api/chunk/") :])
                rec = corpus.read_record(chunk_id)
                if rec is None:
                    self._send_json({"error": f"Chunk not found: {chunk_id}"}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(rec)
                return

            if path == "/api/search":
                q = qs.get("q", [""])[0].strip()
                cat = qs.get("category", [None])[0] or None
                book = qs.get("book", [None])[0] or None
                status = qs.get("status", [None])[0] or None
                limit = min(int(qs.get("limit", ["15"])[0]), 40)
                if not q:
                    self._send_json({"expansion": {"id_terms": [], "ar_terms": [], "concepts": []}, "hits": []})
                    return
                self._send_json(
                    corpus.search(
                        query=q,
                        category=cat,
                        book_title=book,
                        verification_status=status,
                        limit=limit,
                    )
                )
                return

            self._serve_static(path)

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON body"}, HTTPStatus.BAD_REQUEST)
                return

            if parsed.path == "/api/rag/index":
                include_hadith = bool(body.get("include_hadith", False))
                try:
                    if isinstance(corpus.vector_store, PgVectorStore):
                        corpus.vector_store.ensure_schema()
                    paths = default_dataset_paths(corpus.repo_root, include_hadith=include_hadith)
                    idx_stats = index_jsonl_files(
                        paths,
                        store=corpus.vector_store,
                        embed_client=corpus.embed_client,
                        model=corpus.settings.embedding_model,
                    )
                    self._send_json({
                        "status": "ok",
                        "backend": corpus.settings.vector_backend,
                        "model": corpus.settings.embedding_model,
                        "scanned": idx_stats.scanned,
                        "embedded": idx_stats.embedded,
                        "skipped_unchanged": idx_stats.skipped_unchanged,
                        "total_in_store": idx_stats.total_in_store,
                    })
                except (OpenAICompatError, psycopg.Error, OSError, RuntimeError, ValueError) as exc:
                    self._send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return

            if parsed.path != "/api/ask":
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return

            query = str(body.get("query", "")).strip()
            if not query:
                self._send_json({"error": "Query cannot be empty"}, HTTPStatus.BAD_REQUEST)
                return

            min_score = float(body.get("min_score", 0.65))
            category = body.get("category") or None
            result = run_grounded_qa(corpus, query=query, min_score=min_score, category=category)
            self._send_json(result)

    return JamiyyahHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jamiyyah Prototype API + Web UI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--no-hadith", action="store_true", help="Skip background loading of hadits.jsonl")
    args = parser.parse_args()

    corpus = CorpusIndex(_REPO_ROOT)
    corpus.load_default_datasets(include_hadith=not args.no_hadith)

    web_dir = _resolve_web_dir()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(corpus, web_dir))
    print(f"Jamiyyah Prototype UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Jamiyyah server...")
        server.server_close()


if __name__ == "__main__":
    main()
