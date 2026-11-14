"""Parser for raw Hadith CSV files (columns: Perawi, Arab, Terjemahan)."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from jamiyyah_normalizer import build_embedding_text, normalize_arabic
from jamiyyah_parsers.base import BaseParser, slugify

_HADITH_LABEL_RE = re.compile(r"^(?:Hadits\s+)?(.+?)\s+Nomor\s+(\d+)$", re.IGNORECASE)


def _split_perawi_label(label: str) -> Tuple[str, Optional[str]]:
    match = _HADITH_LABEL_RE.match(label.strip())
    if not match:
        return label.strip(), None
    return match.group(1).strip(), match.group(2)


class HadithCsvParser(BaseParser):
    """Parse Hadith CSV files into Jamiyyah Canonical Schema JSONL records."""

    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader, start=1):
                label = (row.get("Perawi") or "").strip()
                arabic_raw = (row.get("Arab") or "").strip()
                indonesian = (row.get("Terjemahan") or "").strip()
                if not label or not arabic_raw:
                    continue

                collection, number = _split_perawi_label(label)
                collection_slug = slugify(collection) or "hadith"
                num_part = number or str(idx)
                doc_id = f"hadith_{collection_slug}_{num_part}"
                chunk_id = f"{doc_id}_c01"

                hierarchy = ["Hadits", collection, label]
                arabic_clean = normalize_arabic(arabic_raw)
                embedding_text = build_embedding_text(
                    source_category="hadith",
                    hierarchy=hierarchy,
                    context=indonesian,
                    arabic_text=arabic_raw,
                )

                metadata: Dict[str, Any] = {
                    "collection": collection,
                    "verification_status": "pending",
                    "footnotes": [],
                    "referenced_books": [{"title": collection}],
                }
                if number is not None:
                    metadata["hadith_number"] = int(number)

                yield {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "source_category": "hadith",
                    "language": "mixed" if indonesian else "ar",
                    "hierarchy": hierarchy,
                    "content": {
                        "arabic_raw": arabic_raw,
                        "arabic_clean": arabic_clean,
                        "indonesian": indonesian,
                        "embedding_text": embedding_text,
                    },
                    "citation": {
                        "short_label": label,
                        "full_reference": f"{label} ({collection})",
                    },
                    "metadata": metadata,
                }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse Hadith CSV to Jamiyyah JSONL.")
    parser.add_argument("input_csv", type=Path, help="Path to unparsed hadits.csv")
    parser.add_argument("output_jsonl", type=Path, help="Destination parsed JSONL path")
    args = parser.parse_args()

    count = HadithCsvParser().export_jsonl(args.input_csv, args.output_jsonl)
    print(f"Exported {count} hadith records to {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
