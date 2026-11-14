"""Placeholder parser for Maktabah Shamela (.bok / SQLite) sources."""

from pathlib import Path
from typing import Any, Dict, Iterator

from jamiyyah_parsers.base import BaseParser


class ShamelaParser(BaseParser):
    """Extract Kitab Turats hierarchy, matan, syarah, and footnotes from Shamela DB."""

    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            "Shamela parser is not implemented yet. "
            "Target inputs: .bok / exported SQLite databases."
        )
