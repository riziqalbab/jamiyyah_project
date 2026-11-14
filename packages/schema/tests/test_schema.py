import unittest

from jamiyyah_schema.validate import SchemaValidationError, validate_record


def _sample_record() -> dict:
    return {
        "chunk_id": "bm_pwnu_jatim_2023_012_c01",
        "doc_id": "bm_pwnu_jatim_2023_012",
        "source_category": "bahtsul_masail",
        "language": "mixed",
        "hierarchy": ["Bahtsul Masail PWNU Jawa Timur", "Muamalah"],
        "content": {
            "arabic_raw": "وَكُلُّ قَرْضٍ جَرَّ مَنْفَعَةً فَهُوَ رِبًا",
            "arabic_clean": "وكل قرض جر منفعة فهو ربا",
            "indonesian": "Setiap pinjaman yang menarik manfaat adalah riba.",
            "embedding_text": "Kategori: Bahtsul Masail | Hierarki: Muamalah",
        },
        "citation": {
            "short_label": "BM PWNU Jatim (2023)",
            "full_reference": "LBM PWNU Jawa Timur (2023)",
            "url": "https://nu.or.id",
        },
        "metadata": {
            "verification_status": "pending",
            "footnotes": [],
            "referenced_books": [{"title": "Hasyiyah Al-Bajuri", "juz": 1, "page": 365}],
        },
    }


class TestCanonicalSchema(unittest.TestCase):
    def test_valid_record_passes(self) -> None:
        validated = validate_record(_sample_record())
        self.assertEqual(validated["chunk_id"], "bm_pwnu_jatim_2023_012_c01")

    def test_invalid_source_category_raises(self) -> None:
        bad = _sample_record()
        bad["source_category"] = "unknown_source"
        with self.assertRaises(SchemaValidationError):
            validate_record(bad)

    def test_empty_hierarchy_raises(self) -> None:
        bad = _sample_record()
        bad["hierarchy"] = []
        with self.assertRaises(SchemaValidationError):
            validate_record(bad)


if __name__ == "__main__":
    unittest.main()
