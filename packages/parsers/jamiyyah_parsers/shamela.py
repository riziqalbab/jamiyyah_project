"""Parser for cached Maktabah Shamela web book pages."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from bs4 import BeautifulSoup
from jamiyyah_normalizer import build_embedding_text, normalize_arabic

from jamiyyah_parsers.base import BaseParser, slugify

_DEFAULT_SOURCE_URL = "https://shamela.ws/book/35120"
_TERMINAL_PUNCT = frozenset({".", "!", "؟", ":"})


@dataclass
class ShamelaParagraph:
    """Merged Arabic paragraph extracted from one or more Shamela pages."""

    text: str
    matan: List[str] = field(default_factory=list)
    shamela_pages: List[int] = field(default_factory=list)
    kitab_pages: List[int] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)


@dataclass
class ShamelaSection:
    """Semantic section (Bab / Fasal / Sub-chapter) inside a Shamela Kitab."""

    title: str
    kitab_title: str
    paragraphs: List[ShamelaParagraph] = field(default_factory=list)
    has_fasl: bool = False

    @property
    def arabic_raw(self) -> str:
        return "\n".join(p.text for p in self.paragraphs).strip()

    @property
    def matan_arabic(self) -> List[str]:
        items: List[str] = []
        for p in self.paragraphs:
            items.extend(p.matan)
        return items

    @property
    def shamela_pages(self) -> List[int]:
        pages: List[int] = []
        for p in self.paragraphs:
            pages.extend(p.shamela_pages)
        return sorted(set(pages))

    @property
    def kitab_pages(self) -> List[int]:
        pages: List[int] = []
        for p in self.paragraphs:
            pages.extend(p.kitab_pages)
        return sorted(set(pages))

    @property
    def footnotes(self) -> List[str]:
        notes: List[str] = []
        for p in self.paragraphs:
            notes.extend(p.footnotes)
        return notes


@dataclass
class ShamelaKitab:
    """Top-level chapter (Kitab or Muqaddimah) in a Shamela book."""

    title: str
    start_page: int
    sections: List[ShamelaSection] = field(default_factory=list)


@dataclass
class ShamelaBook:
    """Structured representation of a Maktabah Shamela book."""

    book_id: int
    title: str
    base_url: str
    kitabs: List[ShamelaKitab] = field(default_factory=list)


def _resolve_pages_dir(source_path: Path) -> Path:
    if (source_path / "pages").is_dir():
        return source_path / "pages"
    return source_path


def _sorted_html_files(pages_dir: Path) -> List[Tuple[int, Path]]:
    numbered: List[Tuple[int, Path]] = []
    for path in pages_dir.glob("*.html"):
        stem = path.stem
        if stem.isdigit():
            numbered.append((int(stem), path))
    numbered.sort(key=lambda item: item[0])
    if not numbered:
        raise FileNotFoundError(f"No numbered Shamela HTML pages found in {pages_dir}")
    return numbered


def _extract_top_kitab_toc(
    numbered_files: List[Tuple[int, Path]],
    book_id: int,
) -> List[Tuple[int, str]]:
    """Extract top-level Kitab entries (start_page, title) from .s-nav sidebar links."""
    first_html = numbered_files[0][1].read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(first_html, "html.parser")
    prefix = f"/book/{book_id}/"
    kitab_entries: List[Tuple[int, str]] = []
    seen_pages = set()
    for anchor in soup.select(".s-nav a[href]"):
        href = anchor["href"]
        if prefix not in href:
            continue
        tail = href.rstrip("/").split("/")[-1]
        if not tail.isdigit():
            continue
        title = anchor.get_text(" ", strip=True)
        if not title or title.startswith("•"):
            continue
        pid = int(tail)
        if pid not in seen_pages:
            seen_pages.add(pid)
            kitab_entries.append((pid, title))
    kitab_entries.sort(key=lambda item: item[0])
    return kitab_entries


def _clean_paragraph_element(p_tag: Any) -> Tuple[str, List[str], bool]:
    """Strip Shamela UI buttons/anchors and return (text, matan_spans, is_c4_heading)."""
    for ui in p_tag.select("a.btn_tag, span.anchor"):
        ui.decompose()
    text = p_tag.get_text(" ", strip=True)
    if not text:
        return "", [], False
    matan = [sp.get_text(" ", strip=True) for sp in p_tag.select("span.c2") if sp.get_text(strip=True)]
    c4_tags = [sp.get_text(" ", strip=True) for sp in p_tag.select("span.c4") if sp.get_text(strip=True)]
    is_c4_heading = bool(c4_tags and text == " ".join(c4_tags)) or (
        text.startswith("[") and text.endswith("]") and len(text) < 120
    )
    return text, matan, is_c4_heading


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip("[]• ")).strip()


def _kitab_index_for_page(page_id: int, kitab_starts: List[Tuple[int, str]]) -> int:
    idx = 0
    for i, (start_pid, _) in enumerate(kitab_starts):
        if page_id >= start_pid:
            idx = i
    return idx


def _flush_pending(section: Optional[ShamelaSection], pending: Optional[ShamelaParagraph]) -> None:
    if section is not None and pending is not None and pending.text.strip():
        section.paragraphs.append(pending)


def _flush_section(kitab: Optional[ShamelaKitab], section: Optional[ShamelaSection]) -> None:
    if kitab is not None and section is not None and section.paragraphs:
        kitab.sections.append(section)


def _should_skip_unbracketed_kitab_header(text: str, kitab_title: str) -> bool:
    """Skip unbracketed title-only <p> duplicates on pages like 142 and 296."""
    norm_t = normalize_arabic(text).replace(" ", "")
    norm_k = normalize_arabic(kitab_title).replace(" ", "")
    return len(norm_t) >= 6 and norm_t in norm_k and len(text) < 90


def extract_shamela_book(
    source_path: Path,
    book_id: int = 35120,
    book_title: str = "Fathul Qarib al-Mujib",
    base_url: Optional[str] = None,
    min_fasl_split_chars: int = 200,
) -> ShamelaBook:
    """Parse cached Shamela HTML pages into Kitab -> Section -> Paragraph hierarchy."""
    pages_dir = _resolve_pages_dir(source_path)
    numbered_files = _sorted_html_files(pages_dir)
    resolved_base_url = (base_url or f"https://shamela.ws/book/{book_id}").rstrip("/")

    kitab_toc = _extract_top_kitab_toc(numbered_files, book_id=book_id)
    if not kitab_toc:
        kitab_toc = [(numbered_files[0][0], book_title)]

    kitabs = [ShamelaKitab(title=title, start_page=spid) for spid, title in kitab_toc]
    cur_kidx = 0
    cur_section: Optional[ShamelaSection] = None
    pending: Optional[ShamelaParagraph] = None

    for page_id, html_path in numbered_files:
        kidx = _kitab_index_for_page(page_id, kitab_toc)
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        nass = soup.select_one(".nass")
        if nass is None:
            continue
        raw_pnum = nass.get("data-page-num")
        kitab_page = int(raw_pnum) if raw_pnum and str(raw_pnum).isdigit() else page_id

        page_footnotes = [
            fn.get_text(" ", strip=True)
            for fn in soup.select(".hamesh")
            if fn.get_text(" ", strip=True)
        ]

        if kidx != cur_kidx:
            _flush_pending(cur_section, pending)
            pending = None
            _flush_section(kitabs[cur_kidx], cur_section)
            cur_section = None
            cur_kidx = kidx

        kitab_obj = kitabs[kidx]

        for p_idx, p_tag in enumerate(nass.find_all("p")):
            text, matan, is_heading = _clean_paragraph_element(p_tag)
            if not text:
                continue

            if p_idx <= 1 and _should_skip_unbracketed_kitab_header(text, kitab_obj.title):
                continue

            # Keep opening Basmalah inside the first section instead of creating a tiny standalone chunk
            if page_id == numbered_files[0][0] and p_idx == 0 and text.startswith("بسم الله"):
                if cur_section is None:
                    cur_section = ShamelaSection(title=kitab_obj.title, kitab_title=kitab_obj.title)
                cur_section.paragraphs.append(
                    ShamelaParagraph(
                        text=text,
                        matan=matan,
                        shamela_pages=[page_id],
                        kitab_pages=[kitab_page],
                    )
                )
                continue

            if is_heading:
                _flush_pending(cur_section, pending)
                pending = None
                heading_title = _normalize_heading(text)
                if (
                    cur_section is not None
                    and len(cur_section.paragraphs) == 1
                    and cur_section.paragraphs[0].text.startswith("بسم الله")
                ):
                    cur_section.title = heading_title
                    continue
                _flush_section(kitab_obj, cur_section)
                cur_section = ShamelaSection(
                    title=heading_title,
                    kitab_title=kitab_obj.title,
                )
                continue

            if cur_section is None:
                cur_section = ShamelaSection(title=kitab_obj.title, kitab_title=kitab_obj.title)

            # Split distinct {فصل} blocks when current section already holds substantive prose
            if text.startswith("{فصل}") and (cur_section.paragraphs or pending is not None):
                _flush_pending(cur_section, pending)
                pending = None
                existing_chars = sum(len(p.text) for p in cur_section.paragraphs)
                if existing_chars >= min_fasl_split_chars:
                    _flush_section(kitab_obj, cur_section)
                    cur_section = ShamelaSection(
                        title=f"{cur_section.title} (فصل)",
                        kitab_title=kitab_obj.title,
                        has_fasl=True,
                    )

            if "{فصل}" in text:
                cur_section.has_fasl = True

            # Merge mid-sentence continuations split across Shamela HTML page breaks
            if pending is not None and p_idx == 0:
                prev_tail = pending.text.rstrip()
                if prev_tail and prev_tail[-1] not in _TERMINAL_PUNCT:
                    pending.text = f"{prev_tail} {text}"
                    pending.matan.extend(matan)
                    if page_id not in pending.shamela_pages:
                        pending.shamela_pages.append(page_id)
                    if kitab_page not in pending.kitab_pages:
                        pending.kitab_pages.append(kitab_page)
                    continue

            _flush_pending(cur_section, pending)
            notes = page_footnotes if p_idx == 0 else []
            pending = ShamelaParagraph(
                text=text,
                matan=matan,
                shamela_pages=[page_id],
                kitab_pages=[kitab_page],
                footnotes=list(notes),
            )

    _flush_pending(cur_section, pending)
    _flush_section(kitabs[cur_kidx], cur_section)

    return ShamelaBook(
        book_id=book_id,
        title=book_title,
        base_url=resolved_base_url,
        kitabs=[k for k in kitabs if k.sections],
    )


class ShamelaParser(BaseParser):
    """Extract Kitab Turats hierarchy, matan, syarah, and footnotes from cached Shamela HTML."""

    def __init__(
        self,
        book_id: int = 35120,
        book_title: str = "Fathul Qarib al-Mujib",
        author: str = "Muhammad bin Qasim Al-Ghazi",
        madzhab: str = "Syafi'i",
        base_url: Optional[str] = None,
        verification_status: str = "pending",
    ) -> None:
        self.book_id = book_id
        self.book_title = book_title
        self.author = author
        self.madzhab = madzhab
        self.base_url = (base_url or f"https://shamela.ws/book/{book_id}").rstrip("/")
        self.verification_status = verification_status

    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        book = extract_shamela_book(
            source_path=source_path,
            book_id=self.book_id,
            book_title=self.book_title,
            base_url=self.base_url,
        )
        book_slug = slugify(self.book_title)
        for k_idx, kitab in enumerate(book.kitabs, start=1):
            for s_idx, section in enumerate(kitab.sections, start=1):
                arabic_raw = section.arabic_raw
                if not arabic_raw:
                    continue
                arabic_clean = normalize_arabic(arabic_raw)
                hierarchy = [self.book_title, kitab.title]
                if section.title != kitab.title:
                    hierarchy.append(section.title)
                spages = section.shamela_pages
                first_spage = spages[0] if spages else kitab.start_page
                kpages = section.kitab_pages
                page_label = f"hal. {kpages[0]}" if kpages else f"Shamela hal. {first_spage}"
                doc_id = f"turats_{book_slug}_k{k_idx:02d}"
                chunk_id = f"{doc_id}_s{s_idx:03d}"

                yield {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "source_category": "kitab_turats",
                    "language": "ar",
                    "hierarchy": hierarchy,
                    "content": {
                        "arabic_raw": arabic_raw,
                        "arabic_clean": arabic_clean,
                        "indonesian": "",
                        "embedding_text": build_embedding_text(
                            source_category="kitab_turats",
                            hierarchy=hierarchy,
                            arabic_text=arabic_raw,
                        ),
                    },
                    "citation": {
                        "short_label": f"{self.book_title} ({page_label})",
                        "full_reference": (
                            f"{self.book_title} — {self.author}, {kitab.title} / {section.title} ({page_label})"
                        ),
                        "url": f"{book.base_url}/{first_spage}",
                    },
                    "metadata": {
                        "madzhab": self.madzhab,
                        "verification_status": self.verification_status,
                        "footnotes": section.footnotes,
                        "referenced_books": [
                            {
                                "title": self.book_title,
                                "author": self.author,
                                "page": kpages[0] if kpages else first_spage,
                            }
                        ],
                        "matan_arabic": section.matan_arabic,
                        "shamela_pages": spages,
                        "kitab_pages": kpages,
                    },
                }


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse cached Shamela HTML pages into Canonical JSONL.")
    parser.add_argument("input_dir", type=Path, help="Path to cached Shamela pages directory")
    parser.add_argument("output_jsonl", type=Path, help="Output .jsonl path")
    parser.add_argument("--book-id", type=int, default=35120)
    parser.add_argument("--book-title", default="Fathul Qarib al-Mujib")
    args = parser.parse_args()

    shamela = ShamelaParser(book_id=args.book_id, book_title=args.book_title)
    count = shamela.export_jsonl(args.input_dir, args.output_jsonl, validate=True)
    print(f"Exported {count} validated records to {args.output_jsonl}")


if __name__ == "__main__":
    main()
