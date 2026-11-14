"""Document and dataset parsers for Jamiyyah Project."""

from jamiyyah_parsers.base import BaseParser
from jamiyyah_parsers.fathul_qarib import FathulQaribParser
from jamiyyah_parsers.hadith_csv import HadithCsvParser
from jamiyyah_parsers.shamela import ShamelaParser
from jamiyyah_parsers.taqrib import TaqribParser

__all__ = [
    "BaseParser",
    "FathulQaribParser",
    "HadithCsvParser",
    "ShamelaParser",
    "TaqribParser",
]
