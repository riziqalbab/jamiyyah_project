"""Canonical JSONL schema validator (uses Pydantic when installed, stdlib otherwise)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

SOURCE_CATEGORIES = frozenset({
    "bahtsul_masail",
    "kitab_turats",
    "hadith",
    "quran_tafsir",
    "fatwa",
    "qawaid_fiqh",
})

VERIFICATION_STATUSES = frozenset({
    "pending",
    "machine_verified",
    "scholarly_verified",
    "rejected",
})

LANGUAGE_VALUES = frozenset({"ar", "id", "mixed"})


class SchemaValidationError(ValueError):
    """Raised when a dataset record violates the Jamiyyah Canonical Schema."""


def _require_non_empty_str(obj: Dict[str, Any], key: str, prefix: str = "") -> None:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise SchemaValidationError(f"'{prefix}{key}' must be a non-empty string")


def _validate_stdlib(record: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(record, dict):
        raise SchemaValidationError("Record must be a JSON object")

    _require_non_empty_str(record, "chunk_id")
    _require_non_empty_str(record, "doc_id")

    if record.get("source_category") not in SOURCE_CATEGORIES:
        raise SchemaValidationError(
            f"'source_category' must be one of {sorted(SOURCE_CATEGORIES)}"
        )
    if record.get("language") not in LANGUAGE_VALUES:
        raise SchemaValidationError(f"'language' must be one of {sorted(LANGUAGE_VALUES)}")

    hierarchy = record.get("hierarchy")
    if not isinstance(hierarchy, list) or not hierarchy or not all(
        isinstance(item, str) and item.strip() for item in hierarchy
    ):
        raise SchemaValidationError("'hierarchy' must be a non-empty list of strings")

    content = record.get("content")
    if not isinstance(content, dict):
        raise SchemaValidationError("'content' must be an object")
    for field in ("arabic_raw", "arabic_clean"):
        if not isinstance(content.get(field), str):
            raise SchemaValidationError(f"'content.{field}' must be a string")
    if "indonesian" in content and not isinstance(content["indonesian"], str):
        raise SchemaValidationError("'content.indonesian' must be a string")
    _require_non_empty_str(content, "embedding_text", prefix="content.")

    citation = record.get("citation")
    if not isinstance(citation, dict):
        raise SchemaValidationError("'citation' must be an object")
    _require_non_empty_str(citation, "short_label", prefix="citation.")
    _require_non_empty_str(citation, "full_reference", prefix="citation.")
    if "url" in citation and citation["url"] is not None and not isinstance(citation["url"], str):
        raise SchemaValidationError("'citation.url' must be a string or null")

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise SchemaValidationError("'metadata' must be an object")
    status = metadata.get("verification_status", "pending")
    if status not in VERIFICATION_STATUSES:
        raise SchemaValidationError(
            f"'metadata.verification_status' must be one of {sorted(VERIFICATION_STATUSES)}"
        )
    if "footnotes" in metadata and not isinstance(metadata["footnotes"], list):
        raise SchemaValidationError("'metadata.footnotes' must be a list")
    if "referenced_books" in metadata:
        books = metadata["referenced_books"]
        if not isinstance(books, list):
            raise SchemaValidationError("'metadata.referenced_books' must be a list")
        for idx, book in enumerate(books):
            if not isinstance(book, dict):
                raise SchemaValidationError(f"'metadata.referenced_books[{idx}]' must be an object")
            _require_non_empty_str(book, "title", prefix=f"metadata.referenced_books[{idx}].")

    return record


def validate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single canonical record dict."""
    try:
        from jamiyyah_schema.models import JamiyyahChunk
    except ImportError:
        return _validate_stdlib(record)

    try:
        return JamiyyahChunk.model_validate(record).model_dump()
    except Exception as exc:
        raise SchemaValidationError(str(exc)) from exc


def validate_jsonl_file(path: Path) -> Tuple[int, List[str]]:
    """Validate every non-empty line in a JSONL file. Returns (count, errors)."""
    errors: List[str] = []
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            count += 1
            try:
                payload = json.loads(line)
                validate_record(payload)
            except (json.JSONDecodeError, SchemaValidationError) as exc:
                errors.append(f"Line {line_no}: {exc}")
    return count, errors


def main(argv: List[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python3 -m jamiyyah_schema.validate <file.jsonl> [...]", file=sys.stderr)
        return 2

    has_error = False
    for target in args:
        path = Path(target)
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            has_error = True
            continue
        count, errors = validate_jsonl_file(path)
        if errors:
            has_error = True
            print(f"FAILED {path} ({len(errors)}/{count} invalid):")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK {path} ({count} records validated)")

    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
