"""Arabic text normalization per Jamiyyah Canonical Schema rules.

Preserves original text separately as ``arabic_raw`` and produces a search-ready
``arabic_clean`` representation by stripping harakat/tatweel and unifying Alif/Ya.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Tashkeel / Harakat + Quranic annotation marks
_HARAKAT_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL_RE = re.compile(r"\u0640+")
_WHITESPACE_RE = re.compile(r"\s+")

_CHAR_TRANSLATION = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ى": "ي",
    "ی": "ي",
})

_CATEGORY_LABELS = {
    "bahtsul_masail": "Bahtsul Masail",
    "kitab_turats": "Kitab Turats",
    "hadith": "Hadits",
    "quran_tafsir": "Qur'an & Tafsir",
    "fatwa": "Fatwa",
    "qawaid_fiqh": "Qawaid Fiqhiyyah",
}


def normalize_arabic(text: str) -> str:
    """Return ``arabic_clean`` without mutating the caller's ``arabic_raw`` string."""
    if not text:
        return ""
    cleaned = _HARAKAT_RE.sub("", text)
    cleaned = _TATWEEL_RE.sub("", cleaned)
    cleaned = cleaned.translate(_CHAR_TRANSLATION)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def build_embedding_text(
    source_category: str,
    hierarchy: Iterable[str],
    arabic_text: str,
    context: Optional[str] = None,
) -> str:
    """Construct the structured ``content.embedding_text`` field."""
    category_label = _CATEGORY_LABELS.get(source_category, source_category)
    hierarchy_str = " > ".join(part.strip() for part in hierarchy if part and part.strip())

    parts = [f"Kategori: {category_label}"]
    if hierarchy_str:
        parts.append(f"Hierarki:\n{hierarchy_str}")
    if context and context.strip():
        parts.append(f"Konteks:\n{context.strip()}")
    if arabic_text and arabic_text.strip():
        parts.append(f"Ibarat:\n{arabic_text.strip()}")
    return "\n\n".join(parts)
