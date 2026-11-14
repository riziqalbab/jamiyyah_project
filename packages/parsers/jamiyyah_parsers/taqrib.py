"""Bilingual parser for Matan al-Ghayah wat-Taqrib PDF (Arabic + Indonesian)."""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
from jamiyyah_normalizer import build_embedding_text, normalize_arabic

from jamiyyah_parsers.base import BaseParser, slugify
from jamiyyah_parsers.fathul_qarib import clean_indonesian_text

_DEFAULT_SOURCE_URL = "https://www.facebook.com/groups/konsultasiagamaislam"

# Single-codepoint ToUnicode overrides for Ghostscript-subsetted TimesNewRoman Arabic fonts.
_SINGLE_CHAR_CMAP: dict[int, str] = {
    0x0003: " ",
    0x0005: '"',
    0x000A: "'",
    0x000B: ")",
    0x000C: "(",
    0x000F: ",",
    0x0011: ".",
    0x0014: "1",
    0x0015: "2",
    0x0016: "3",
    0x0017: "4",
    0x001D: ":",
    0x003F: "\\",
    0x02EC: "\u060c",  # Arabic comma
    0x02EF: "\u0621",  # Hamza
    0x02F2: "\u064c",  # Dammatan
    0x02F4: "\u064e",  # Fatha
    0x02F5: "\u064f",  # Damma
    0x02F6: "\u0650",  # Kasra
    0x02F8: "\u0652",  # Sukun
    0x0349: "\u0651",  # Shadda
}

# Visual-order ligatures so MuPDF's visual-to-logical RTL reordering yields logical Arabic.
_LIGATURE_CMAP: dict[int, str] = {
    0x037F: "\u0647\u0644\u0644",        # لله
    0x0BCC: "\u0647\u0644\u0644\u0627",  # الله
    0x03F5: "\u0622\u0644",              # لآ
    0x03F6: "\u0622\u0644",
    0x03F7: "\u0623\u0644",              # لأ
    0x03F8: "\u0623\u0644",
    0x03F9: "\u0625\u0644",              # لإ
    0x03FA: "\u0625\u0644",
    0x03FB: "\u0627\u0644",              # لا
    0x03FC: "\u0627\u0644",
}

_KITAB_TITLE_MAP: Sequence[tuple[str, str]] = (
    ("مقدمة", "Muqaddimah"),
    ("كتاب الطهارة", "Kitab Thaharah"),
    ("كتاب الصلاة", "Kitab Shalat"),
    ("كتاب الزكاة", "Kitab Zakat"),
    ("كتاب الصيام", "Kitab Puasa"),
    ("كتاب الحج", "Kitab Haji"),
    ("كتاب البيوع", "Kitab Jual Beli & Muamalah"),
    ("كتاب الفرائض", "Kitab Faraidl & Wasiat"),
    ("باب النكاح", "Kitab Nikah"),
    ("كتاب الجنايات", "Kitab Jinayat"),
    ("كتاب الحدود", "Kitab Hudud"),
    ("كتاب الجهاد", "Kitab Jihad"),
    ("كتاب الصيد والذبائح", "Kitab Buruan & Sembelihan"),
    ("كتاب السبق والرمي", "Kitab Perlombaan & Memanah"),
    ("كتاب الأيمان والنذور", "Kitab Sumpah & Nadzar"),
    ("كتاب الأقضية والشهادات", "Kitab Peradilan & Persaksian"),
    ("كتاب العتق", "Kitab Memerdekakan Budak"),
)

_TOUNICODE_RE = re.compile(r"/ToUnicode\s+(\d+)\s+0\s+R")
_AR_CHAR_RE = re.compile(r"[\u0600-\u06FF]")
_LATIN_ALNUM_RE = re.compile(r"[A-Za-z0-9]")
_PUNCT_ONLY_RE = re.compile(r'^[\s"\'.,:;\\§]+$')
_RULE_SEP_RE = re.compile(r"^[-=*]{3,}$")
_FOOTNOTE_ITEM_RE = re.compile(r"^\[(\d+)\]\s*")
_LEADING_TRANSLATION_RE = re.compile(r"^(?:Terjemah|Artinya)\s*:\s*", re.IGNORECASE)
_ID_HEADING_PREFIX_RE = re.compile(
    r'^["\(]?(?:KITAB|BAB|PASAL|FASAL|FASL|FSAL)\b["\)]?', re.IGNORECASE
)
_COLOPHON_RE = re.compile(
    r"^(?:BY SUIM WAHYUDI|Published by:|https?://www\.facebook\.com/groups/konsultasiagamaislam"
    r"|Selesai Pada hari senin|Mohon Koreksi Ulang)",
    re.IGNORECASE,
)


@dataclass
class _VisualLine:
    """Single reconstructed line from the PDF with layout metadata."""

    page: int
    oy: int
    kind: str  # "AR", "ID", "MIX"
    text: str
    bold: bool
    x0: float
    x1: float
    spans: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _Segment:
    """Contiguous run of Arabic or Indonesian lines."""

    kind: str  # "AR" or "ID"
    lines: list[_VisualLine]


@dataclass
class TaqribSection:
    """Parsed bilingual section of Matan al-Ghayah wat-Taqrib."""

    kitab_idx: int
    kitab_title_id: str
    kitab_title_ar: str
    heading_id: str | None
    arabic_raw: str
    indonesian: str
    pdf_pages: list[int]
    footnotes: list[str] = field(default_factory=list)


def build_taqrib_tounicode_cmap() -> bytes:
    """Construct the corrected ToUnicode CMap for Taqrib PDF Arabic fonts."""
    mapping: dict[int, str] = dict(_SINGLE_CHAR_CMAP)
    for cid in range(0x0381, 0x03F5):
        mapping[cid] = unicodedata.normalize("NFKC", chr(cid + 0xFB00))
    mapping.update(_LIGATURE_CMAP)

    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CMapType 2 def",
        "/CMapName/FixedTaqribAr def",
        "1 begincodespacerange",
        "<0000><ffff>",
        "endcodespacerange",
    ]
    items = sorted(mapping.items())
    for idx in range(0, len(items), 100):
        batch = items[idx : idx + 100]
        lines.append(f"{len(batch)} beginbfchar")
        for cid, uni in batch:
            hex_uni = "".join(f"{ord(ch):04x}" for ch in uni)
            lines.append(f"<{cid:04x}><{hex_uni}>")
        lines.append("endbfchar")
    lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end end"])
    return "\n".join(lines).encode("ascii")


def open_taqrib_pdf(pdf_path: Path) -> pymupdf.Document:
    """Open ``taqrib.pdf`` and patch broken Arabic ToUnicode CMaps in memory."""
    doc = pymupdf.open(pdf_path)
    cmap_bytes = build_taqrib_tounicode_cmap()
    patched_xrefs = set()

    for page in doc:
        for font_info in page.get_fonts():
            fxref, _, ftype, basefont = font_info[:4]
            if ftype != "Type0" or "TimesNewRoman" not in basefont or "GXLINZ" in basefont:
                continue
            if fxref in patched_xrefs:
                continue
            patched_xrefs.add(fxref)
            match = _TOUNICODE_RE.search(doc.xref_object(fxref))
            if match:
                doc.update_stream(int(match.group(1)), cmap_bytes)
    return doc


def _has_arabic(text: str) -> bool:
    return bool(_AR_CHAR_RE.search(text))


def _join_spans(spans: Sequence[dict[str, Any]], rtl: bool) -> str:
    ordered = sorted(spans, key=lambda sp: -sp["bbox"][2] if rtl else sp["bbox"][0])
    parts: list[str] = []
    prev_edge: float | None = None
    for span in ordered:
        txt = span.get("text", "")
        if not txt.strip():
            continue
        if prev_edge is not None:
            gap = (prev_edge - span["bbox"][2]) if rtl else (span["bbox"][0] - prev_edge)
            if gap > 1.5 and parts and not (parts[-1].endswith(" ") or txt.startswith(" ")):
                parts.append(" ")
        parts.append(txt)
        prev_edge = span["bbox"][0] if rtl else span["bbox"][2]
    joined = "".join(parts)
    return re.sub(r"\s+", " ", joined).strip()


def _extract_visual_lines(doc: pymupdf.Document) -> list[_VisualLine]:
    vlines: list[_VisualLine] = []
    for pno, page in enumerate(doc, start=1):
        rows: dict[int, list[dict[str, Any]]] = {}
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "")
                    if not txt.strip() or "Wingdings" in span.get("font", ""):
                        continue
                    oy = round(span["origin"][1] / 5.0) * 5
                    rows.setdefault(oy, []).append(span)

        for oy in sorted(rows):
            sps = rows[oy]
            ar_sps = [s for s in sps if _has_arabic(s["text"])]
            lat_sps = [
                s for s in sps if not _has_arabic(s["text"]) and _LATIN_ALNUM_RE.search(s["text"])
            ]
            x0 = min(s["bbox"][0] for s in sps)
            x1 = max(s["bbox"][2] for s in sps)
            bold = all(
                ("Bold" in s.get("font", "") or bool(s.get("flags", 0) & 16))
                for s in sps
                if s["text"].strip()
            )

            if ar_sps and not lat_sps:
                txt = _join_spans(sps, rtl=True)
                if not _has_arabic(txt):
                    continue
                kind = "AR"
            elif ar_sps and lat_sps:
                lat_txt = clean_indonesian_text(_join_spans(lat_sps, rtl=False))
                ar_txt = _join_spans(ar_sps, rtl=True)
                if len(ar_txt) <= 2 and len(lat_txt) > 5:
                    txt, kind = lat_txt, "ID"
                else:
                    txt, kind = f"{lat_txt} {ar_txt}".strip(), "MIX"
            else:
                txt = clean_indonesian_text(_join_spans(sps, rtl=False))
                if not txt:
                    continue
                kind = "ID"

            vlines.append(
                _VisualLine(
                    page=pno,
                    oy=oy,
                    kind=kind,
                    text=txt,
                    bold=bold,
                    x0=x0,
                    x1=x1,
                    spans=sps,
                )
            )

    _fix_rtl_indonesian_paragraphs(vlines)
    return vlines


def _fix_rtl_indonesian_paragraphs(vlines: list[_VisualLine]) -> None:
    """Re-join Indonesian lines that were typeset in Word RTL paragraph mode."""
    para: list[_VisualLine] = []

    def _flush() -> None:
        if not para:
            return
        is_rtl_para = any(
            (ln.x1 >= 534.0 and ln.x0 >= 120.0)
            or (ln.x1 >= 539.0 and ln.x0 > 74.0 and len(ln.spans) > 1)
            for ln in para
        )
        if is_rtl_para:
            for ln in para:
                if ln.kind == "ID":
                    ln.text = clean_indonesian_text(_join_spans(ln.spans, rtl=True))

    for ln in vlines:
        if ln.kind == "AR":
            _flush()
            para = []
        else:
            if para and (ln.page != para[-1].page or (ln.oy - para[-1].oy) >= 22):
                _flush()
                para = []
            para.append(ln)
    _flush()


def _group_segments(vlines: Sequence[_VisualLine]) -> list[_Segment]:
    segs: list[_Segment] = []
    cur_kind: str | None = None
    cur_lines: list[_VisualLine] = []

    for ln in vlines:
        if ln.kind == "ID" and _PUNCT_ONLY_RE.match(ln.text):
            continue
        seg_kind = "AR" if ln.kind == "AR" else "ID"
        if seg_kind != cur_kind:
            if cur_lines and cur_kind is not None:
                segs.append(_Segment(kind=cur_kind, lines=cur_lines))
            cur_kind = seg_kind
            cur_lines = [ln]
        else:
            cur_lines.append(ln)

    if cur_lines and cur_kind is not None:
        segs.append(_Segment(kind=cur_kind, lines=cur_lines))
    return segs


def _clean_arabic_segment_lines(lines: Sequence[_VisualLine]) -> str:
    texts = [ln.text.replace("§", "").strip() for ln in lines]
    texts = [t for t in texts if t]
    if texts:
        # Recover Word cursor-misplaced trailing فصل on the first line (e.g. p.50 Wasiat)
        first = re.sub(r"^[.,،]+\s*", "", texts[0])
        if not first.startswith(("فصل", "(فصل)", '"فصل"', "( فصل )")) and first.endswith(" فصل"):
            first = '"فصل" ' + first[: -len(" فصل")].strip()
        texts[0] = first
    return "\n".join(texts).strip()


def _is_trailing_heading_line(ln: _VisualLine) -> bool:
    txt = ln.text.replace("§", "").strip()
    if not txt or _RULE_SEP_RE.match(txt):
        return False
    if _ID_HEADING_PREFIX_RE.match(txt):
        return True
    if ln.bold and len(txt) <= 85:
        if txt.isupper() and any(ch.isalpha() for ch in txt):
            return True
        if txt.endswith(":") and len(txt.split()) <= 5:
            return True
    return False


def _format_heading_title(raw: str) -> str:
    cleaned = raw.replace("§", "").strip()
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    if re.fullmatch(r'["\(]?(?:FASAL|FASL|FSAL)["\)]?', cleaned, re.IGNORECASE):
        return "Fasal"
    if cleaned.isupper():
        words = cleaned.split()
        minor = {"dan", "yang", "di", "ke", "dari", "pada", "atau", "dalam", "untuk", "saat", "bagi"}
        out = []
        for i, word in enumerate(words):
            if word.startswith("(") and len(word) > 1:
                inner = word[1:]
                out.append(f"({inner.lower().capitalize()}")
            else:
                low = word.lower()
                out.append(low if (i > 0 and low in minor) else low.capitalize())
        return " ".join(out)
    return cleaned


def _split_id_segment(
    lines: Sequence[_VisualLine],
    is_standalone_title: bool = False,
    allow_full_consume: bool = False,
) -> tuple[str, list[str], str | None]:
    """Split an Indonesian segment into (body_text, footnotes, trailing_heading_for_next_ar)."""
    filtered = [ln for ln in lines if not _COLOPHON_RE.match(ln.text)]
    if not filtered:
        return "", [], None

    # 1. Extract trailing heading lines belonging to the NEXT Arabic segment.
    trailing_heading: str | None = None
    if not is_standalone_title:
        trailing_lines: list[_VisualLine] = []
        idx = len(filtered) - 1
        while idx >= 0 and _is_trailing_heading_line(filtered[idx]):
            if idx > 0 and filtered[idx].page == filtered[idx - 1].page:
                gap = filtered[idx].oy - filtered[idx - 1].oy
                if gap < 22 and not _is_trailing_heading_line(filtered[idx - 1]):
                    break
            trailing_lines.append(filtered[idx])
            idx -= 1
            if (
                idx >= 0
                and filtered[idx].page == filtered[idx + 1].page
                and (filtered[idx + 1].oy - filtered[idx].oy) >= 22
            ):
                break
        if trailing_lines:
            trailing_lines.reverse()
            if idx >= 0:
                trailing_heading = _format_heading_title(" ".join(ln.text for ln in trailing_lines))
                filtered = filtered[: idx + 1]
            elif allow_full_consume and len(trailing_lines) == len(filtered):
                trailing_heading = _format_heading_title(" ".join(ln.text for ln in trailing_lines))
                return "", [], trailing_heading

    # 2. Separate footnotes (CATATAN / --- / === boxes / [n] notes) from body lines.
    body_lines: list[_VisualLine] = []
    fn_groups: list[str] = []
    in_box_fn = False
    in_numbered_fn = False
    cur_fn_parts: list[str] = []

    def _flush_fn() -> None:
        nonlocal cur_fn_parts
        if cur_fn_parts:
            fn_groups.append(clean_indonesian_text(" ".join(cur_fn_parts)))
            cur_fn_parts = []

    for ln in filtered:
        txt = ln.text.replace("§", "").strip()
        if not txt:
            continue

        if _RULE_SEP_RE.match(txt):
            if in_box_fn:
                _flush_fn()
                in_box_fn = False
                in_numbered_fn = False
            else:
                in_box_fn = True
            continue

        if txt.upper() in {"CATATAN:", "CATATAN."}:
            _flush_fn()
            in_numbered_fn = True
            continue

        if in_box_fn:
            if _FOOTNOTE_ITEM_RE.match(txt) or (txt in {"***"}):
                _flush_fn()
                if txt == "***":
                    continue
            cur_fn_parts.append(txt)
            continue

        if _FOOTNOTE_ITEM_RE.match(txt) and ln.x0 < 100.0:
            _flush_fn()
            in_numbered_fn = True
            cur_fn_parts.append(txt)
            continue

        if in_numbered_fn:
            if _is_trailing_heading_line(ln) and not txt.lower().startswith("artinya:"):
                _flush_fn()
                in_numbered_fn = False
                body_lines.append(ln)
            else:
                cur_fn_parts.append(txt)
            continue

        body_lines.append(ln)

    _flush_fn()

    # 3. Format body lines into clean paragraphs.
    paras: list[str] = []
    cur_para: list[str] = []
    prev_ln: _VisualLine | None = None
    for ln in body_lines:
        txt = ln.text.replace("§", "").strip()
        if not txt:
            continue
        if prev_ln is not None:
            gap = ln.oy - prev_ln.oy if ln.page == prev_ln.page else 999
            is_new_para = gap >= 22 or (
                ln.page != prev_ln.page and cur_para and cur_para[-1].rstrip()[-1:] in '.?!"'
            )
            if is_new_para and cur_para:
                paras.append(" ".join(cur_para))
                cur_para = []
        cur_para.append(txt)
        prev_ln = ln
    if cur_para:
        paras.append(" ".join(cur_para))

    body_text = "\n".join(paras).strip()
    body_text = _LEADING_TRANSLATION_RE.sub("", body_text).strip()
    return body_text, fn_groups, trailing_heading


def _match_kitab_title(arabic_text: str) -> str | None:
    first_line = arabic_text.splitlines()[0].strip()
    for ar_prefix, id_title in _KITAB_TITLE_MAP:
        if first_line.startswith(ar_prefix):
            return id_title
    return None


def _is_standalone_heading_pair(ar_text: str, id_text: str) -> bool:
    if len(ar_text) > 30 or len(id_text) > 60:
        return False
    if ar_text.startswith(("فصل", "(فصل)", '"فصل"', "( فصل )")):
        return False
    if "\n" in ar_text or "." in ar_text.rstrip("."):
        return False
    return id_text.isupper() or bool(_ID_HEADING_PREFIX_RE.match(id_text))


def extract_taqrib_sections(pdf_path: Path) -> list[TaqribSection]:
    """Extract and deduplicate bilingual sections from ``taqrib.pdf``."""
    doc = open_taqrib_pdf(pdf_path)
    vlines = _extract_visual_lines(doc)
    segs = _group_segments(vlines)

    # First pass: collect raw (AR, ID) pairs and record last occurrence index of each normalized AR
    # prefix so duplicated blocks (e.g. Kitab Shalat p.9-11 vs cleaner p.12-13) keep the latest copy.
    raw_pairs: list[tuple[str, Sequence[_VisualLine], Sequence[_VisualLine], str | None]] = []
    pending_heading: str | None = None

    idx = 0
    if segs and segs[0].kind == "ID":
        _, _, pending_heading = _split_id_segment(segs[0].lines, allow_full_consume=True)
        idx = 1

    while idx < len(segs):
        if segs[idx].kind != "AR":
            idx += 1
            continue
        ar_lines = segs[idx].lines
        ar_text = _clean_arabic_segment_lines(ar_lines)
        id_lines: Sequence[_VisualLine] = []
        if idx + 1 < len(segs) and segs[idx + 1].kind == "ID":
            id_lines = segs[idx + 1].lines
            idx += 2
        else:
            idx += 1

        # Drop final colophon ("تم الكتاب", "الحمد لله رب العالمين")
        if ar_text in {"تم الكتاب", "الحمد لله رب العالمين"}:
            continue

        raw_pairs.append((ar_text, ar_lines, id_lines, pending_heading))
        pending_heading = None

    last_sig_idx: dict[str, int] = {}
    sigs: list[str] = []
    for p_idx, (ar_text, _, _, _) in enumerate(raw_pairs):
        sig = normalize_arabic(ar_text)[:90]
        sigs.append(sig)
        last_sig_idx[sig] = p_idx

    sections: list[TaqribSection] = []
    kitab_idx = 0
    cur_kitab_id = "Muqaddimah"
    cur_kitab_ar = "مقدمة"
    cur_sub_heading: str | None = None
    pending_intro_id: str | None = None
    next_heading: str | None = None

    for p_idx, (ar_text, ar_lines, id_lines, initial_heading) in enumerate(raw_pairs):
        if last_sig_idx[sigs[p_idx]] != p_idx:
            # Skip earlier duplicated print (e.g. Kitab Shalat p.9-11), reset heading carryover
            next_heading = None
            continue

        heading_for_this = next_heading or initial_heading
        next_heading = None

        matched_kitab = _match_kitab_title(ar_text)
        if matched_kitab is not None:
            kitab_idx += 1
            cur_kitab_id = matched_kitab
            cur_kitab_ar = ar_lines[0].text.replace("§", "").strip()
            cur_sub_heading = None

        is_title_only_hint = (
            len(ar_lines) == 1
            and len(ar_text) <= 55
            and not ar_text.startswith(("فصل", "(فصل)", '"فصل"', "( فصل )"))
            and "." not in ar_text.rstrip(".")
        )
        id_body, footnotes, trailing_heading = _split_id_segment(
            id_lines, is_standalone_title=is_title_only_hint
        )
        next_heading = trailing_heading

        # If a Kitab title block carries only the title (e.g. "كتاب الجنايات" + "Kitab Jinayat"),
        # advance hierarchy without emitting a tiny empty-content chunk.
        if matched_kitab is not None and is_title_only_hint:
            # Special case: Kitab Hudud has an Arabic-less Indonesian intro paragraph before its first pair.
            if id_body and _format_heading_title(id_body) != _format_heading_title(cur_kitab_id):
                # Strip leading Kitab title line if present
                body_lines_split = id_body.splitlines()
                if body_lines_split and _ID_HEADING_PREFIX_RE.match(body_lines_split[0]):
                    rest = "\n".join(body_lines_split[1:]).strip()
                    if rest:
                        pending_intro_id = rest
            continue

        # Strip leading Arabic Kitab title line when the first prose paragraph immediately follows it
        if matched_kitab is not None and len(ar_lines) > 1:
            ar_split = ar_text.splitlines()
            if len(ar_split) > 1 and ar_split[0].strip() == cur_kitab_ar:
                ar_text = "\n".join(ar_split[1:]).strip()

        if _is_standalone_heading_pair(ar_text, id_body):
            cur_sub_heading = f"{_format_heading_title(id_body)} ({ar_text})"
            continue

        is_new_fasal = bool(re.match(r'^[\s."\'\(]*فصل\b', ar_text))
        if is_new_fasal:
            cur_sub_heading = None

        # Promote leading heading line (e.g. "Fasal", "I'TIKAF", "SYARAT BOLEHNYA TAYAMMUM")
        sec_heading = heading_for_this or cur_sub_heading
        if id_body:
            id_body = re.sub(r"^[.,]+\s*", "", id_body).strip()
            id_split = id_body.splitlines()
            first_id = id_split[0].strip() if id_split else ""
            is_leading_heading = bool(first_id) and len(id_split) > 1 and (
                (_ID_HEADING_PREFIX_RE.match(first_id) and len(first_id) <= 60)
                or (first_id.isupper() and any(ch.isalpha() for ch in first_id) and len(first_id) <= 85)
            )
            if is_leading_heading:
                if not sec_heading or sec_heading.lower() == "fasal":
                    sec_heading = _format_heading_title(first_id)
                id_body = "\n".join(id_split[1:]).strip()
                id_body = _LEADING_TRANSLATION_RE.sub("", id_body).strip()
                id_body = re.sub(r"^[.,]+\s*", "", id_body).strip()
        if is_new_fasal and not sec_heading:
            sec_heading = "Fasal"

        if pending_intro_id:
            id_body = f"{pending_intro_id}\n{id_body}".strip()
            pending_intro_id = None

        pages = sorted({ln.page for ln in ar_lines} | {ln.page for ln in id_lines})
        sections.append(
            TaqribSection(
                kitab_idx=max(kitab_idx, 1),
                kitab_title_id=cur_kitab_id,
                kitab_title_ar=cur_kitab_ar,
                heading_id=sec_heading,
                arabic_raw=ar_text,
                indonesian=id_body,
                pdf_pages=pages,
                footnotes=footnotes,
            )
        )

    return sections


class TaqribParser(BaseParser):
    """Parse Matan al-Ghayah wat-Taqrib PDF into Canonical JSONL."""

    def __init__(
        self,
        book_title: str = "Matan al-Ghayah wat-Taqrib",
        author: str = "Abu Syuja' Ahmad bin Al-Husain Al-Asfahani",
        translator: str = "Suim Wahyudi, S.Pd.I",
        madzhab: str = "Syafi'i",
        source_url: str = _DEFAULT_SOURCE_URL,
        verification_status: str = "pending",
    ) -> None:
        self.book_title = book_title
        self.author = author
        self.translator = translator
        self.madzhab = madzhab
        self.source_url = source_url
        self.verification_status = verification_status

    def _resolve_pdf_path(self, source_path: Path) -> Path:
        pdf_path = (source_path / "taqrib.pdf") if source_path.is_dir() else source_path
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        return pdf_path

    def parse(self, source_path: Path) -> Iterator[dict[str, Any]]:
        pdf_path = self._resolve_pdf_path(source_path)
        sections = extract_taqrib_sections(pdf_path)

        book_slug = slugify(self.book_title)
        per_kitab_counter: dict[int, int] = {}

        for sec in sections:
            per_kitab_counter[sec.kitab_idx] = per_kitab_counter.get(sec.kitab_idx, 0) + 1
            sec_num = per_kitab_counter[sec.kitab_idx]
            doc_id = f"turats_{book_slug}_k{sec.kitab_idx:02d}"
            chunk_id = f"{doc_id}_c{sec_num:03d}"

            level_kitab = (
                f"{sec.kitab_title_id} ({sec.kitab_title_ar})"
                if sec.kitab_title_ar
                else sec.kitab_title_id
            )
            hierarchy = [self.book_title, level_kitab]
            if sec.heading_id and sec.heading_id.lower() not in {
                sec.kitab_title_id.lower(),
                "pendahuluan",
            }:
                hierarchy.append(sec.heading_id)

            arabic_clean = normalize_arabic(sec.arabic_raw)
            page_str = (
                f"hal. {sec.pdf_pages[0]}"
                if len(sec.pdf_pages) <= 1
                else f"hal. {sec.pdf_pages[0]}-{sec.pdf_pages[-1]}"
            )
            leaf_label = sec.heading_id or sec.kitab_title_id

            yield {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "source_category": "kitab_turats",
                "language": "mixed",
                "hierarchy": hierarchy,
                "content": {
                    "arabic_raw": sec.arabic_raw,
                    "arabic_clean": arabic_clean,
                    "indonesian": sec.indonesian,
                    "embedding_text": build_embedding_text(
                        source_category="kitab_turats",
                        hierarchy=hierarchy,
                        arabic_text=sec.arabic_raw,
                        context=sec.indonesian,
                    ),
                },
                "citation": {
                    "short_label": f"{self.book_title} - {sec.kitab_title_id} ({page_str})",
                    "full_reference": (
                        f"{self.book_title} — {self.author}, {level_kitab} > {leaf_label} "
                        f"(PDF {page_str}; Terj. {self.translator})"
                    ),
                    "url": self.source_url,
                },
                "metadata": {
                    "madzhab": self.madzhab,
                    "verification_status": self.verification_status,
                    "footnotes": sec.footnotes,
                    "referenced_books": [
                        {
                            "title": self.book_title,
                            "author": self.author,
                            "page": sec.pdf_pages[0] if sec.pdf_pages else 1,
                        }
                    ],
                    "pdf_pages": sec.pdf_pages,
                    "translator": self.translator,
                },
            }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Matan al-Ghayah wat-Taqrib PDF into Canonical JSONL."
    )
    parser.add_argument(
        "source_path",
        type=Path,
        help="Path to datasets/unparsed/kitab_turats/taqrib directory or taqrib.pdf",
    )
    parser.add_argument("output_jsonl", type=Path, help="Output .jsonl path")
    args = parser.parse_args()

    taqrib = TaqribParser()
    count = taqrib.export_jsonl(args.source_path, args.output_jsonl, validate=True)
    print(f"Exported {count} validated records to {args.output_jsonl}")


if __name__ == "__main__":
    main()
