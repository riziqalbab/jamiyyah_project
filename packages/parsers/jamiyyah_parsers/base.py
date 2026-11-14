"""Shared parser contract and JSONL export helpers."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterator

from jamiyyah_schema import validate_record

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Create a deterministic lowercase ASCII identifier fragment."""
    return _SLUG_RE.sub("_", text.lower()).strip("_")


class BaseParser(ABC):
    """Base interface for all Jamiyyah source parsers."""

    @abstractmethod
    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        """Yield Canonical Schema records from ``source_path``."""

    def export_jsonl(self, source_path: Path, output_path: Path, validate: bool = True) -> int:
        """Write parsed records to ``output_path`` as JSONL and return record count."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with output_path.open("w", encoding="utf-8") as handle:
            for record in self.parse(source_path):
                if validate:
                    validate_record(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count
