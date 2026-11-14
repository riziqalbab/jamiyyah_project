"""Bilingual parser aligning Shamela #35120 Arabic text with Fathul Qarib Indonesian PDF."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import pymupdf
from jamiyyah_normalizer import build_embedding_text, normalize_arabic

from jamiyyah_parsers.base import BaseParser, slugify
from jamiyyah_parsers.shamela import (
    ShamelaBook,
    ShamelaParagraph,
    ShamelaSection,
    extract_shamela_book,
)

# Bilingual Arabic-root <-> Indonesian fiqh anchor concepts for alignment & swap verification.
_FIQH_CONCEPTS: Tuple[Tuple[str, str], ...] = (
    (r"مياه|ماء", r"\bair\b"),
    (r"ثلاثة|ثلاث", r"\btiga\b"),
    (r"اربعة|اربع", r"\bempat\b"),
    (r"خمسة|خمس", r"\blima\b"),
    (r"ستة|ست", r"\benam\b"),
    (r"سبعة|سبع", r"\btujuh\b"),
    (r"ثمانية|ثمان", r"\bdelapan\b"),
    (r"عشرة|عشر", r"\bsepuluh\b"),
    (r"قلتين", r"qullah"),
    (r"جلود|جلد|دباغ", r"kulit|samak|dibagh"),
    (r"اواني|اناء", r"wadah|perabot|bejana"),
    (r"ذهب|فضة", r"emas|perak"),
    (r"سواك", r"siwak"),
    (r"وضوء", r"wudlu|wudhu"),
    (r"استنجاء", r"istinja"),
    (r"غسل", r"mandi"),
    (r"خفين", r"muza|khuf"),
    (r"تيمم", r"tayammum|tayamum"),
    (r"جبائر|جبيرة", r"jaba.?ir|perban"),
    (r"نجاسة|نجاس", r"najis"),
    (r"كلب|خنزير", r"anjing|babi"),
    (r"خمر", r"khamr|arak"),
    (r"حيض|نفاس|استحاضة", r"haid|nifas|istihad"),
    (r"قبلة", r"kiblat|qiblat"),
    (r"سجود السهو|السهو", r"sujud sahwi|sahwi"),
    (r"جماعة", r"jama.?ah"),
    (r"مسافر|قصر|جمع", r"musafir|qashar|jama"),
    (r"جمعة", r"jum.?at|jumat"),
    (r"عيدين", r"idul|hari raya|idain"),
    (r"كسوف|خسوف", r"gerhana|kusuf"),
    (r"استسقاء", r"istisqa|hujan"),
    (r"خوف", r"khauf"),
    (r"ميت|كفن|جناز", r"jenazah|mayit|kafan"),
    (r"ابل", r"onta|unta"),
    (r"بقر", r"\bsapi\b"),
    (r"غنم|شاة", r"kambing|domba"),
    (r"خلط|خليطان", r"persero|khulthah|campur"),
    (r"زروع|ثمار|وسق", r"pertanian|buah|wasaq"),
    (r"تجارة", r"dagangan|perdagangan"),
    (r"معدن|ركاز", r"tambang|rikaz|pendam"),
    (r"فطر", r"fitrah"),
    (r"اصناف|فقراء|مساكين", r"golongan|fakir|miskin"),
    (r"اعتكاف", r"i.?tikaf|itikaf"),
    (r"حج|عمرة|احرام|طواف|سعي|وقوف", r"haji|umrah|ihram|thawaf|sa.?i|wuquf"),
    (r"دماء|فدية", r"dam|denda|fidyah"),
    (r"ربا", r"\briba\b"),
    (r"خيار", r"khiyar"),
    (r"سلم", r"\bsalam\b"),
    (r"رهن", r"gadai|rahn"),
    (r"حجر|مفلس", r"hajr|mahjur|pailit"),
    (r"صلح", r"damai|shulh"),
    (r"حوالة", r"hiwalah|alih hutang"),
    (r"ضمان|كفالة", r"dlaman|jaminan|kafalah"),
    (r"شركة", r"syirkah|perseroan"),
    (r"وكالة", r"wakalah|perwakilan"),
    (r"اقرار", r"iqrar|pengakuan"),
    (r"عارية", r"ariyah|pinjam"),
    (r"غصب", r"ghashab|merampas"),
    (r"شفعة", r"syuf.?ah"),
    (r"قراض", r"qiradl|mudharabah"),
    (r"مساقاة", r"musaqah"),
    (r"اجارة", r"ijarah|sewa"),
    (r"جعالة", r"ji.?alah|sayembara"),
    (r"موات", r"mawat|tanah mati"),
    (r"وقف", r"wakaf|waqaf"),
    (r"هبة", r"hibah"),
    (r"لقطة", r"luqathah|temuan"),
    (r"لقيط", r"laqith|anak temuan"),
    (r"وديعة", r"wadi.?ah|titipan"),
    (r"فرائض|ميراث|عصبة", r"faraidl|waris|ashabah"),
    (r"وصية|وصايا", r"wasiat"),
    (r"نكاح|خطبة|محرمات", r"nikah|khitbah|mahram"),
    (r"صداق|مهر", r"mahar|maskawin"),
    (r"وليمة", r"walimah"),
    (r"قسم|نشوز", r"gilir|nusyuz"),
    (r"خلع", r"khulu"),
    (r"طلاق|رجعة", r"thalaq|talak|ruju"),
    (r"ايلاء", r"\bila"),
    (r"ظهار", r"dzihar|zhihar"),
    (r"لعان", r"li.?an"),
    (r"عدة|احداد", r"iddah|ihdad"),
    (r"رضاع", r"radla|susuan"),
    (r"نفقة|حضانة", r"nafkah|nafaqah|hadlanah"),
    (r"جنايات|قتل|قصاص", r"jinayat|pembunuhan|qishash"),
    (r"دية|عاقلة", r"diyat|aqilah"),
    (r"قسامة", r"qasamah"),
    (r"زنا|احصان", r"\bzina\b|ihshan"),
    (r"قذف", r"qadzaf|menuduh"),
    (r"خمر|مسكر", r"minuman keras|memabukkan"),
    (r"سرقة", r"curi|pencurian"),
    (r"قاطع الطريق|حرابة", r"begal|perampok"),
    (r"صيال", r"menyerang|shiyal"),
    (r"بغاة", r"pemberontak|bughat"),
    (r"ردة", r"murtad|riddah"),
    (r"تارك الصلاة", r"meninggalkan sholat"),
    (r"جهاد|جزية", r"jihad|jizyah"),
    (r"صيد|ذبائح", r"buruan|sembelih"),
    (r"اضحية|ضحايا", r"kurban|qurban|udhiyah"),
    (r"عقيقة", r"aqiqah|akikah"),
    (r"اطعمه|اطعم", r"makanan"),
    (r"سبق|رمي|مسابقة", r"lomba|panah"),
    (r"ايمان|يمين", r"sumpah"),
    (r"نذر", r"nadzar|nazar"),
    (r"قضاء|قاضي", r"qadla|hakim"),
    (r"شهادات|شهادة", r"saksi|persaksian"),
    (r"دعوى|بينات", r"gugatan|bukti"),
    (r"عتق|ولاء", r"merdeka|budak|wala"),
    (r"تدبير|ام الولد|مكاتب", r"mudabbar|ummul walad|mukatab"),
)

_COMPILED_CONCEPTS = [(re.compile(ar_p), re.compile(id_p)) for ar_p, id_p in _FIQH_CONCEPTS]
_FASAL_START_RE = re.compile(r"^\(?[FP]asal\b", re.IGNORECASE)
_FOOTNOTE_START_RE = re.compile(r"^(?:(\d+)\s*)?\[(\d+)\]")
_INLINE_FN_REF_RE = re.compile(r"(?:(\d+)\s*)?\[(\d+)\]")


@dataclass
class PdfUnit:
    """Paragraph-level Indonesian unit extracted from the left column of the PDF."""

    text: str
    pages: List[int]
    heading: Optional[str] = None
    is_bab: bool = False
    is_sub: bool = False
    is_fasal: bool = False


@dataclass
class PdfKitab:
    """Top-level chapter in the Indonesian PDF translation."""

    title: str
    units: List[PdfUnit] = field(default_factory=list)


@dataclass
class PdfBook:
    """Extracted Indonesian translation and footnotes from Fathul Qarib PDF."""

    kitabs: List[PdfKitab] = field(default_factory=list)
    footnotes_by_page: Dict[int, List[Tuple[str, str]]] = field(default_factory=dict)


@dataclass
class AlignedChunk:
    """Aligned bilingual section ready for Canonical JSONL serialization."""

    kitab_idx: int
    kitab_title_id: str
    kitab_title_ar: str
    section_title_ar: str
    pdf_heading: Optional[str]
    arabic_raw: str
    matan_arabic: List[str]
    indonesian: str
    shamela_pages: List[int]
    kitab_pages: List[int]
    pdf_pages: List[int]
    footnotes: List[str]
    alignment_method: str


def _has_arabic_codepoints(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if (0x0600 <= code <= 0x06FF) or (0x0750 <= code <= 0x077F) or (0xFB50 <= code <= 0xFEFF):
            return True
    return False


def clean_indonesian_text(text: str) -> str:
    """Normalize PDF smart-quote artifacts and whitespace."""
    cleaned = (
        text.replace("„", "'")
        .replace("‟", "'")
        .replace("‚", "'")
        .replace("‛", "'")
        .replace("\u00a0", " ")
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _format_kitab_title(raw_title: str) -> str:
    if raw_title == "Muqaddimah":
        return raw_title
    words = raw_title.split()
    formatted = []
    for idx, word in enumerate(words):
        low = word.lower()
        if idx > 0 and low in {"dan", "yang", "di", "ke", "dari", "pada"}:
            formatted.append(low)
        else:
            formatted.append(low.capitalize())
    return " ".join(formatted)


def _join_row_spans(spans: Sequence[Dict[str, Any]]) -> str:
    parts: List[str] = []
    prev_x1: Optional[float] = None
    for span in spans:
        txt = span["text"]
        if (
            prev_x1 is not None
            and span["bbox"][0] - prev_x1 > 1.5
            and parts
            and not (parts[-1].endswith(" ") or txt.startswith(" "))
        ):
            parts.append(" ")
        parts.append(txt)
        prev_x1 = span["bbox"][2]
    return clean_indonesian_text("".join(parts))


def _extract_muqaddimah_units(doc: pymupdf.Document, max_page: int) -> List[PdfUnit]:
    units: List[PdfUnit] = []
    for pno in range(1, max_page + 1):
        page = doc[pno - 1]
        tables = page.find_tables()
        if tables.tables:
            for row in tables.tables[0].extract():
                cell_text = clean_indonesian_text(row[0] or "")
                if cell_text:
                    units.append(
                        PdfUnit(
                            text=cell_text,
                            pages=[pno],
                            heading="Muqaddimah",
                            is_sub=(len(units) == 0),
                        )
                    )
            continue
        # Fallback for PDFs whose Muqaddimah is plain left-column text without table borders
        min_y = 215.0 if pno == 1 else 0.0
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                left_spans = [
                    sp for sp in line.get("spans", [])
                    if sp.get("text", "").strip()
                    and sp["bbox"][0] < 350
                    and sp["bbox"][1] >= min_y
                    and not (sp["bbox"][1] > 725 and sp["text"].strip().isdigit())
                    and not _has_arabic_codepoints(sp["text"])
                ]
                if not left_spans:
                    continue
                txt = _join_row_spans(left_spans)
                if txt and not txt.startswith("KITAB "):
                    units.append(
                        PdfUnit(
                            text=txt,
                            pages=[pno],
                            heading="Muqaddimah",
                            is_sub=(len(units) == 0),
                        )
                    )
    return units


def _collect_page_footnotes(fn_rows: Dict[int, List[Dict[str, Any]]]) -> List[Tuple[str, str]]:
    """Merge multi-line size<=9.5 footnote rows into (marker, full_note_text) pairs."""
    notes: List[Tuple[str, str]] = []
    cur_marker = ""
    cur_parts: List[str] = []
    for yb in sorted(fn_rows):
        sps = sorted(fn_rows[yb], key=lambda s: s["bbox"][0])
        line_text = _join_row_spans(sps)
        if not line_text:
            continue
        match = _FOOTNOTE_START_RE.match(line_text)
        if match:
            if cur_parts:
                notes.append((cur_marker, clean_indonesian_text(" ".join(cur_parts))))
            cur_marker = f"[{match.group(2)}]"
            cur_parts = [line_text]
        else:
            cur_parts.append(line_text)
    if cur_parts:
        notes.append((cur_marker, clean_indonesian_text(" ".join(cur_parts))))
    return notes


def _deduplicate_kitab_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop duplicate consecutively-printed sections (e.g., BAB ZAKAT PERSERO on PDF p.115-116)."""
    groups: List[Dict[str, Any]] = []
    cur_group: Dict[str, Any] = {"heading": None, "items": []}
    for item in items:
        if item["type"] in ("BAB", "SUB"):
            if cur_group["items"] or cur_group["heading"]:
                groups.append(cur_group)
            cur_group = {"heading": item["text"], "items": [item]}
        else:
            cur_group["items"].append(item)
    if cur_group["items"] or cur_group["heading"]:
        groups.append(cur_group)

    seen_sigs = set()
    deduped: List[Dict[str, Any]] = []
    for group in groups:
        body = " ".join(x["text"] for x in group["items"] if x["type"] == "PARA").strip()
        sig = (group["heading"], body[:120])
        if body and len(body) > 80:
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)
        deduped.extend(group["items"])
    return deduped


def _rows_to_pdf_units(body_rows: List[Tuple[int, int, float, bool, str]]) -> List[PdfUnit]:
    items: List[Dict[str, Any]] = []
    cur_lines: List[str] = []
    cur_pages: List[int] = []
    prev_y: Optional[int] = None
    prev_pno: Optional[int] = None

    for pno, yb, size, all_bold, text in body_rows:
        if all_bold:
            if cur_lines:
                items.append(
                    {"type": "PARA", "pages": sorted(set(cur_pages)), "text": " ".join(cur_lines)}
                )
                cur_lines, cur_pages = [], []
            kind = "BAB" if size >= 13.0 else "SUB"
            if (
                items
                and items[-1]["type"] == kind
                and items[-1]["pages"][-1] == pno
                and prev_y is not None
                and (yb - prev_y) < 22
            ):
                items[-1]["text"] += f" {text}"
            else:
                items.append({"type": kind, "pages": [pno], "text": text})
            prev_y, prev_pno = yb, pno
            continue

        new_para = False
        if not cur_lines:
            new_para = True
        elif prev_pno is not None and pno != prev_pno:
            prev_tail = cur_lines[-1].rstrip()
            if prev_tail and prev_tail[-1] in '.?!"':
                new_para = True
        elif prev_y is not None and (yb - prev_y) >= 22:
            new_para = True

        if new_para and cur_lines:
            items.append(
                {"type": "PARA", "pages": sorted(set(cur_pages)), "text": " ".join(cur_lines)}
            )
            cur_lines, cur_pages = [], []

        cur_lines.append(text)
        cur_pages.append(pno)
        prev_y, prev_pno = yb, pno

    if cur_lines:
        items.append({"type": "PARA", "pages": sorted(set(cur_pages)), "text": " ".join(cur_lines)})

    dedup_items = _deduplicate_kitab_items(items)
    units: List[PdfUnit] = []
    cur_heading: Optional[str] = None
    pending_bab = False
    pending_sub = False
    for item in dedup_items:
        if item["type"] == "BAB":
            cur_heading = item["text"]
            pending_bab = True
        elif item["type"] == "SUB":
            cur_heading = item["text"]
            pending_sub = True
        else:
            units.append(
                PdfUnit(
                    text=item["text"],
                    pages=item["pages"],
                    heading=cur_heading,
                    is_bab=pending_bab,
                    is_sub=pending_sub,
                    is_fasal=bool(_FASAL_START_RE.match(item["text"])),
                )
            )
            pending_bab = False
            pending_sub = False
    return units


def _find_first_kitab_page(doc: pymupdf.Document) -> int:
    """Locate the 1-based page where the first bold size>=13 KITAB heading appears."""
    for pno, page in enumerate(doc, start=1):
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    is_bold = (span.get("flags", 0) & 16) or ("Bold" in span.get("font", ""))
                    if is_bold and round(span.get("size", 0), 1) >= 13.0 and txt.startswith("KITAB "):
                        return pno
    return 1


def extract_pdf_book(pdf_path: Path) -> PdfBook:
    """Extract left-column Indonesian translation, headings, and footnotes from Fathul Qarib PDF."""
    doc = pymupdf.open(pdf_path)
    first_kitab_page = _find_first_kitab_page(doc)
    muq_max_page = first_kitab_page if (first_kitab_page > 1 and doc[first_kitab_page - 1].find_tables().tables) else max(first_kitab_page - 1, 1)
    muq_units = _extract_muqaddimah_units(doc, max_page=muq_max_page)

    rows: List[Tuple[int, int, float, bool, str]] = []
    footnotes_by_page: Dict[int, List[Tuple[str, str]]] = {}

    for pno in range(first_kitab_page, len(doc) + 1):
        page = doc[pno - 1]
        min_y = 0.0
        if pno == first_kitab_page:
            tables = page.find_tables()
            if tables.tables:
                min_y = max(t.bbox[3] for t in tables.tables) + 2.0
        fn_rows: Dict[int, List[Dict[str, Any]]] = {}
        body_rows: Dict[int, List[Dict[str, Any]]] = {}

        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if not txt.strip():
                        continue
                    x0, y0 = span["bbox"][0], span["bbox"][1]
                    if y0 < min_y:
                        continue
                    if y0 > 725 and txt.strip().isdigit():
                        continue
                    if x0 >= 350 or _has_arabic_codepoints(txt):
                        continue
                    yb = round(y0 / 4.0) * 4
                    if span.get("size", 11.0) <= 9.5:
                        fn_rows.setdefault(yb, []).append(span)
                    else:
                        body_rows.setdefault(yb, []).append(span)

        page_fns = _collect_page_footnotes(fn_rows)
        if page_fns:
            footnotes_by_page[pno] = page_fns

        for yb in sorted(body_rows):
            sps = sorted(body_rows[yb], key=lambda s: s["bbox"][0])
            line_text = _join_row_spans(sps)
            if not line_text:
                continue
            max_sz = max(round(s.get("size", 0), 1) for s in sps)
            non_ref = [s for s in sps if not re.fullmatch(r"[\[\]\d\s]+", s["text"].strip())]
            all_bold = bool(non_ref) and all(
                (s.get("flags", 0) & 16) or ("Bold" in s.get("font", "")) for s in non_ref
            )
            rows.append((pno, yb, max_sz, all_bold, line_text))

    kitab_starts = [
        idx for idx, (_, _, sz, bold, txt) in enumerate(rows)
        if bold and sz >= 13.0 and txt.startswith("KITAB ")
    ]
    kitab_starts.append(len(rows))

    kitabs: List[PdfKitab] = [PdfKitab(title="Muqaddimah", units=muq_units)]
    for k in range(len(kitab_starts) - 1):
        sl = rows[kitab_starts[k] : kitab_starts[k + 1]]
        kitab_title = _format_kitab_title(sl[0][4])
        units = _rows_to_pdf_units(sl[1:])
        kitabs.append(PdfKitab(title=kitab_title, units=units))

    return PdfBook(kitabs=kitabs, footnotes_by_page=footnotes_by_page)


def _ar_concept_mask(text: str) -> int:
    norm = normalize_arabic(text)
    mask = 0
    for idx, (ar_re, _) in enumerate(_COMPILED_CONCEPTS):
        if ar_re.search(norm):
            mask |= 1 << idx
    return mask


def _id_concept_mask(text: str) -> int:
    low = text.lower()
    mask = 0
    for idx, (_, id_re) in enumerate(_COMPILED_CONCEPTS):
        if id_re.search(low):
            mask |= 1 << idx
    return mask


def _concept_score(ar_mask: int, id_mask: int) -> float:
    both = (ar_mask & id_mask).bit_count()
    diff = (ar_mask ^ id_mask).bit_count()
    return 2.0 * both - 0.15 * diff


def _dp_align_slices(
    sections: Sequence[ShamelaSection],
    units: Sequence[PdfUnit],
    target_ratio: float,
) -> List[Tuple[int, int]]:
    """Align ordered Shamela sections onto contiguous slices of PDF units."""
    m = len(sections)
    k = len(units)
    if m == 1 or k <= 1:
        return [(0, k)]
    if k < m:
        raise ValueError(f"Cannot align {m} Shamela sections onto {k} PDF units")

    ar_texts = [s.arabic_raw for s in sections]
    s_masks = [_ar_concept_mask(f"{s.title} {ar_texts[idx]}") for idx, s in enumerate(sections)]
    u_masks = [_id_concept_mask(f"{u.heading or ''} {u.text}") for u in units]
    u_lens = [len(u.text) for u in units]

    neg_inf = -1e18
    dp = [[neg_inf] * (k + 1) for _ in range(m + 1)]
    back = [[-1] * (k + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0

    for i in range(1, m + 1):
        sec = sections[i - 1]
        expected_id = max(len(ar_texts[i - 1]), 1) * target_ratio
        sm = s_masks[i - 1]
        min_j = i
        max_j = k - (m - i)
        max_slice_len = max(expected_id * 3.5, 1200.0)

        for j in range(min_j, max_j + 1):
            cur_id_len = 0
            cur_id_mask = 0
            for prev_j in range(j - 1, i - 2, -1):
                cur_id_len += u_lens[prev_j]
                cur_id_mask |= u_masks[prev_j]
                if cur_id_len > max_slice_len and prev_j < j - 1:
                    break
                if dp[i - 1][prev_j] <= neg_inf / 2:
                    continue

                rel_err = abs(cur_id_len - expected_id) / max(expected_id, 150.0)
                len_score = -4.0 * rel_err

                first_u = units[prev_j]
                boundary_score = 0.0
                if sec.has_fasl and (first_u.is_fasal or first_u.is_bab):
                    boundary_score += 4.0
                elif sec.has_fasl and not (first_u.is_fasal or first_u.is_bab):
                    boundary_score -= 2.0
                if first_u.is_sub or first_u.is_bab:
                    boundary_score += 1.0

                c_score = _concept_score(sm, cur_id_mask)
                cand = dp[i - 1][prev_j] + len_score + boundary_score + c_score
                if cand > dp[i][j]:
                    dp[i][j] = cand
                    back[i][j] = prev_j

    ranges: List[Tuple[int, int]] = []
    cur_j = k
    for i in range(m, 0, -1):
        pj = back[i][cur_j]
        if pj < 0:
            raise RuntimeError(f"DP backtracking failed at section {i}/{m}")
        ranges.append((pj, cur_j))
        cur_j = pj
    ranges.reverse()
    return ranges


def _pair_score(
    sec: ShamelaSection,
    units_slice: Sequence[PdfUnit],
    target_ratio: float,
) -> float:
    ar_txt = sec.arabic_raw
    id_txt = " ".join(u.text for u in units_slice)
    expected_id = max(len(ar_txt), 1) * target_ratio
    rel_err = abs(len(id_txt) - expected_id) / max(expected_id, 150.0)
    s_mask = _ar_concept_mask(f"{sec.title} {ar_txt}")
    u_mask = _id_concept_mask(" ".join(f"{u.heading or ''} {u.text}" for u in units_slice))
    return -4.0 * rel_err + _concept_score(s_mask, u_mask)


def _apply_adjacent_swaps(
    sections: Sequence[ShamelaSection],
    units: Sequence[PdfUnit],
    ranges: List[Tuple[int, int]],
    target_ratio: float,
) -> List[Tuple[int, int]]:
    """Correct local edition reorderings (e.g., Zakat Kambing vs Sapi on PDF p.112-113)."""
    swapped = list(ranges)
    for idx in range(len(swapped) - 1):
        s_a, s_b = sections[idx], sections[idx + 1]
        r_a, r_b = swapped[idx], swapped[idx + 1]
        u_a = units[r_a[0] : r_a[1]]
        u_b = units[r_b[0] : r_b[1]]
        cur_score = _pair_score(s_a, u_a, target_ratio) + _pair_score(s_b, u_b, target_ratio)
        alt_score = _pair_score(s_a, u_b, target_ratio) + _pair_score(s_b, u_a, target_ratio)
        if alt_score - cur_score >= 1.5:
            swapped[idx], swapped[idx + 1] = r_b, r_a
    return swapped


def _subsplit_long_section(
    section: ShamelaSection,
    max_ar_chars: int,
) -> List[ShamelaSection]:
    """Group paragraphs of an extra-long Shamela section into ~900-1400 char sub-sections."""
    if len(section.arabic_raw) <= max_ar_chars or len(section.paragraphs) < 4:
        return [section]

    groups: List[List[ShamelaParagraph]] = []
    buf: List[ShamelaParagraph] = []
    buf_len = 0
    target_sub_len = 1100

    for para in section.paragraphs:
        if buf and (buf_len + len(para.text) > target_sub_len or para.text.startswith("{فصل}")) and buf_len >= 450:
            groups.append(buf)
            buf = []
            buf_len = 0
        buf.append(para)
        buf_len += len(para.text)

    if buf:
        if groups and buf_len < 450:
            groups[-1].extend(buf)
        else:
            groups.append(buf)

    if len(groups) == 1:
        return [section]

    return [
        ShamelaSection(
            title=f"{section.title} ({idx})",
            kitab_title=section.kitab_title,
            paragraphs=grp,
            has_fasl=any("{فصل}" in p.text for p in grp),
        )
        for idx, grp in enumerate(groups, start=1)
    ]


def _collect_chunk_footnotes(
    indonesian_text: str,
    pdf_pages: List[int],
    kitab_end_page: int,
    footnotes_by_page: Dict[int, List[Tuple[str, str]]],
    used_footnotes: set[Tuple[int, int]],
) -> List[str]:
    """Attach PDF footnotes referenced by markers (e.g. [1]) on the chunk's pages or nearby end-of-bab pages."""
    if not pdf_pages:
        return []
    markers = [(m.group(1) or "", f"[{m.group(2)}]") for m in _INLINE_FN_REF_RE.finditer(indonesian_text)]
    if not markers:
        return []

    first_p = min(pdf_pages)
    last_p = max(pdf_pages)
    search_end = min(kitab_end_page, last_p + 5)

    attached: List[str] = []
    for raw_prefix, bracket_marker in markers:
        full_prefix = f"{raw_prefix}{bracket_marker}" if raw_prefix else bracket_marker
        matched_key: Optional[Tuple[int, int]] = None
        matched_text: Optional[str] = None
        for pno in range(first_p, search_end + 1):
            for fn_idx, (fn_marker, fn_text) in enumerate(footnotes_by_page.get(pno, ())):
                key = (pno, fn_idx)
                if key in used_footnotes or fn_marker != bracket_marker:
                    continue
                if raw_prefix and not fn_text.startswith(full_prefix):
                    continue
                matched_key = key
                matched_text = fn_text
                break
            if matched_key is not None:
                break
        if matched_key is not None and matched_text is not None:
            used_footnotes.add(matched_key)
            attached.append(matched_text)
    return attached


def align_fathul_qarib(
    shamela_book: ShamelaBook,
    pdf_book: PdfBook,
    max_section_ar_chars: int = 2600,
) -> List[AlignedChunk]:
    """Align all Kitabs of Shamela #35120 with Fathul Qarib Indonesian PDF."""
    if len(shamela_book.kitabs) != len(pdf_book.kitabs):
        raise ValueError(
            f"Kitab count mismatch: Shamela={len(shamela_book.kitabs)} vs PDF={len(pdf_book.kitabs)}"
        )

    aligned: List[AlignedChunk] = []
    used_footnotes: set[Tuple[int, int]] = set()

    for k_idx, (s_kitab, p_kitab) in enumerate(zip(shamela_book.kitabs, pdf_book.kitabs), start=1):
        s_secs = s_kitab.sections
        p_units = p_kitab.units
        total_ar = sum(len(s.arabic_raw) for s in s_secs)
        total_id = sum(len(u.text) for u in p_units)
        kitab_ratio = total_id / max(total_ar, 1)
        kitab_end_page = max((p for u in p_units for p in u.pages), default=1)

        ranges = _dp_align_slices(s_secs, p_units, target_ratio=kitab_ratio)
        swapped_ranges = _apply_adjacent_swaps(s_secs, p_units, ranges, target_ratio=kitab_ratio)

        for sec_idx, (sec, (a, b)) in enumerate(zip(s_secs, swapped_ranges)):
            was_swapped = swapped_ranges[sec_idx] != ranges[sec_idx]
            slice_units = p_units[a:b]
            sub_secs = _subsplit_long_section(sec, max_ar_chars=max_section_ar_chars)

            if len(sub_secs) > 1 and len(slice_units) >= len(sub_secs):
                section_id_len = sum(len(u.text) for u in slice_units)
                section_ratio = section_id_len / max(len(sec.arabic_raw), 1)
                sub_ranges = _dp_align_slices(sub_secs, slice_units, target_ratio=section_ratio)
                sub_pairs = [
                    (sub_sec, slice_units[sa:sb], "dp_subsplit")
                    for sub_sec, (sa, sb) in zip(sub_secs, sub_ranges)
                ]
            else:
                method = "dp_swapped" if was_swapped else "dp_section"
                sub_pairs = [(sec, slice_units, method)]

            for sub_sec, sub_units, method in sub_pairs:
                arabic_raw = sub_sec.arabic_raw
                id_text = "\n".join(u.text for u in sub_units).strip()
                pdf_pages = sorted({p for u in sub_units for p in u.pages})
                first_heading = next((u.heading for u in sub_units if u.heading), None)
                footnotes = list(sub_sec.footnotes)
                footnotes.extend(
                    _collect_chunk_footnotes(
                        id_text,
                        pdf_pages=pdf_pages,
                        kitab_end_page=kitab_end_page,
                        footnotes_by_page=pdf_book.footnotes_by_page,
                        used_footnotes=used_footnotes,
                    )
                )
                aligned.append(
                    AlignedChunk(
                        kitab_idx=k_idx,
                        kitab_title_id=p_kitab.title,
                        kitab_title_ar=s_kitab.title,
                        section_title_ar=sub_sec.title,
                        pdf_heading=first_heading,
                        arabic_raw=arabic_raw,
                        matan_arabic=sub_sec.matan_arabic,
                        indonesian=id_text,
                        shamela_pages=sub_sec.shamela_pages,
                        kitab_pages=sub_sec.kitab_pages,
                        pdf_pages=pdf_pages,
                        footnotes=footnotes,
                        alignment_method=method,
                    )
                )
    return aligned


class FathulQaribParser(BaseParser):
    """Parse Fathul Qarib combining Shamela #35120 Arabic text and Indonesian PDF."""

    def __init__(
        self,
        shamela_dir: Optional[Path] = None,
        book_id: int = 35120,
        book_title: str = "Fathul Qarib al-Mujib",
        author: str = "Muhammad bin Qasim Al-Ghazi",
        madzhab: str = "Syafi'i",
        max_section_ar_chars: int = 2600,
        verification_status: str = "pending",
    ) -> None:
        self.shamela_dir = shamela_dir
        self.book_id = book_id
        self.book_title = book_title
        self.author = author
        self.madzhab = madzhab
        self.max_section_ar_chars = max_section_ar_chars
        self.verification_status = verification_status

    def _resolve_sources(self, source_path: Path) -> Tuple[Path, Path]:
        if source_path.is_dir():
            pdf_path = source_path / "fathul_qarib.pdf"
            shamela_path = self.shamela_dir or (source_path / f"shamela_{self.book_id}")
        else:
            pdf_path = source_path
            shamela_path = self.shamela_dir or (source_path.parent / f"shamela_{self.book_id}")
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        if not shamela_path.exists():
            raise FileNotFoundError(f"Shamela cache directory not found: {shamela_path}")
        return pdf_path, shamela_path

    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        pdf_path, shamela_path = self._resolve_sources(source_path)
        shamela_book = extract_shamela_book(
            source_path=shamela_path,
            book_id=self.book_id,
            book_title=self.book_title,
        )
        pdf_book = extract_pdf_book(pdf_path)
        aligned_chunks = align_fathul_qarib(
            shamela_book=shamela_book,
            pdf_book=pdf_book,
            max_section_ar_chars=self.max_section_ar_chars,
        )

        book_slug = slugify(self.book_title)
        per_kitab_counter: Dict[int, int] = {}

        for chunk in aligned_chunks:
            per_kitab_counter[chunk.kitab_idx] = per_kitab_counter.get(chunk.kitab_idx, 0) + 1
            sec_num = per_kitab_counter[chunk.kitab_idx]
            doc_id = f"turats_{book_slug}_k{chunk.kitab_idx:02d}"
            chunk_id = f"{doc_id}_c{sec_num:03d}"

            level_kitab = (
                chunk.kitab_title_id
                if chunk.kitab_title_id == "Muqaddimah"
                else f"{chunk.kitab_title_id} ({chunk.kitab_title_ar})"
            )
            if chunk.pdf_heading and chunk.pdf_heading != chunk.kitab_title_id:
                level_sec = f"{_format_kitab_title(chunk.pdf_heading)} ({chunk.section_title_ar})"
            else:
                level_sec = chunk.section_title_ar

            hierarchy = [self.book_title, level_kitab]
            if level_sec and level_sec != level_kitab:
                hierarchy.append(level_sec)

            arabic_clean = normalize_arabic(chunk.arabic_raw)
            first_spage = chunk.shamela_pages[0] if chunk.shamela_pages else 1
            kitab_page_str = (
                f"hal. {chunk.kitab_pages[0]}"
                if len(chunk.kitab_pages) <= 1
                else f"hal. {chunk.kitab_pages[0]}-{chunk.kitab_pages[-1]}"
            )
            pdf_page_str = (
                f"terj. hal. {chunk.pdf_pages[0]}"
                if len(chunk.pdf_pages) <= 1
                else f"terj. hal. {chunk.pdf_pages[0]}-{chunk.pdf_pages[-1]}"
            )

            yield {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "source_category": "kitab_turats",
                "language": "mixed",
                "hierarchy": hierarchy,
                "content": {
                    "arabic_raw": chunk.arabic_raw,
                    "arabic_clean": arabic_clean,
                    "indonesian": chunk.indonesian,
                    "embedding_text": build_embedding_text(
                        source_category="kitab_turats",
                        hierarchy=hierarchy,
                        arabic_text=chunk.arabic_raw,
                        context=chunk.indonesian,
                    ),
                },
                "citation": {
                    "short_label": f"{self.book_title} - {chunk.kitab_title_id} ({kitab_page_str} | {pdf_page_str})",
                    "full_reference": (
                        f"{self.book_title} — {self.author}, {level_kitab} > {level_sec} "
                        f"(Shamela #{self.book_id}, {kitab_page_str}; PDF {pdf_page_str})"
                    ),
                    "url": f"{shamela_book.base_url}/{first_spage}",
                },
                "metadata": {
                    "madzhab": self.madzhab,
                    "verification_status": self.verification_status,
                    "footnotes": chunk.footnotes,
                    "referenced_books": [
                        {
                            "title": self.book_title,
                            "author": self.author,
                            "page": chunk.kitab_pages[0] if chunk.kitab_pages else first_spage,
                        }
                    ],
                    "matan_arabic": chunk.matan_arabic,
                    "shamela_pages": chunk.shamela_pages,
                    "kitab_pages": chunk.kitab_pages,
                    "pdf_pages": chunk.pdf_pages,
                    "alignment_method": chunk.alignment_method,
                },
            }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Fathul Qarib (Shamela #35120 + Indonesian PDF) into Canonical JSONL."
    )
    parser.add_argument(
        "source_path",
        type=Path,
        help="Path to datasets/unparsed/kitab_turats/fathul_qarib directory or PDF file",
    )
    parser.add_argument("output_jsonl", type=Path, help="Output .jsonl path")
    parser.add_argument("--shamela-dir", type=Path, default=None, help="Optional Shamela cache dir")
    args = parser.parse_args()

    fq = FathulQaribParser(shamela_dir=args.shamela_dir)
    count = fq.export_jsonl(args.source_path, args.output_jsonl, validate=True)
    print(f"Exported {count} validated records to {args.output_jsonl}")


if __name__ == "__main__":
    main()
