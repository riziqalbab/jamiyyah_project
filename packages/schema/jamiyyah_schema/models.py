"""Pydantic v2 models for the Jamiyyah Canonical Schema."""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SourceCategory = Literal[
    "bahtsul_masail",
    "kitab_turats",
    "hadith",
    "quran_tafsir",
    "fatwa",
    "qawaid_fiqh",
]

VerificationStatus = Literal[
    "pending",
    "machine_verified",
    "scholarly_verified",
    "rejected",
]

Language = Literal["ar", "id", "mixed"]


class ChunkContent(BaseModel):
    """Normalized and raw textual content for a chunk."""

    arabic_raw: str
    arabic_clean: str
    indonesian: str = ""
    embedding_text: str = Field(min_length=1)


class Citation(BaseModel):
    """Verifiable bibliographic reference metadata."""

    short_label: str = Field(min_length=1)
    full_reference: str = Field(min_length=1)
    url: Optional[str] = None


class ReferencedBook(BaseModel):
    """Classical book or document cited inside a chunk."""

    title: str = Field(min_length=1)
    author: Optional[str] = None
    juz: Optional[int] = Field(default=None, ge=1)
    page: Optional[int] = Field(default=None, ge=1)


class ChunkMetadata(BaseModel):
    """Provenance, verification status, and footnotes."""

    model_config = ConfigDict(extra="allow")

    forum: Optional[str] = None
    year: Optional[int] = None
    madzhab: Optional[str] = None
    verification_status: VerificationStatus = "pending"
    footnotes: List[str] = Field(default_factory=list)
    referenced_books: List[ReferencedBook] = Field(default_factory=list)


class JamiyyahChunk(BaseModel):
    """Canonical record format for all Jamiyyah JSONL datasets."""

    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    source_category: SourceCategory
    language: Language
    hierarchy: List[str] = Field(min_length=1)
    content: ChunkContent
    citation: Citation
    metadata: ChunkMetadata
