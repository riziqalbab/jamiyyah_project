"""Placeholder parser for Bahtsul Masail (NU Online / LBM PWNU / FMPP) sources."""

from pathlib import Path
from typing import Any, Dict, Iterator

from jamiyyah_parsers.base import BaseParser


class BahtsulMasailParser(BaseParser):
    """Extract Bahtsul Masail Q&A cases, ibarat, and forum metadata."""

    def parse(self, source_path: Path) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            "Bahtsul Masail parser is not implemented yet. "
            "Target inputs: structured HTML/JSON scrapes from NU Online, LBM PWNU, FMPP."
        )
