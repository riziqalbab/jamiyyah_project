import unittest

from jamiyyah_normalizer import build_embedding_text, normalize_arabic


class TestArabicNormalizer(unittest.TestCase):
    def test_strips_harakat_tatweel_and_unifies_alif_ya(self) -> None:
        raw = "وَكُـلُّ قَرْضٍ جَرَّ مَنْفَعَةً أَوْ إِضَافَةً إِلَى مُوسَى"
        cleaned = normalize_arabic(raw)
        self.assertEqual(cleaned, "وكل قرض جر منفعة او اضافة الي موسي")
        # Ensure original string remains intact
        self.assertIn("ـ", raw)
        self.assertIn("أ", raw)

    def test_build_embedding_text_includes_hierarchy(self) -> None:
        text = build_embedding_text(
            source_category="kitab_turats",
            hierarchy=["Fathul Mu'in", "Kitab Shalat", "Bab Syarat Shalat"],
            context="Pembahasan mengenai syarat sah pelaksanaan shalat.",
            arabic_text="شروط الصلاة",
        )
        self.assertIn("Kategori: Kitab Turats", text)
        self.assertIn("Fathul Mu'in > Kitab Shalat > Bab Syarat Shalat", text)
        self.assertIn("Ibarat:\nشروط الصلاة", text)


if __name__ == "__main__":
    unittest.main()
