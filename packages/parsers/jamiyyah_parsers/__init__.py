"""Document and dataset parsers for Jamiyyah Project."""

from jamiyyah_parsers.base import BaseParser
from jamiyyah_parsers.hadith_csv import HadithCsvParser

__all__ = ["BaseParser", "HadithCsvParser"]
