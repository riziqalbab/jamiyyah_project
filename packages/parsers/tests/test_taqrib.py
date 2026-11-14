import tempfile
import unittest
from pathlib import Path

from jamiyyah_parsers.taqrib import (
    TaqribParser,
    _fix_rtl_indonesian_paragraphs,
    _format_heading_title,
    _split_id_segment,
    _VisualLine,
    build_taqrib_tounicode_cmap,
)
from jamiyyah_schema.validate import validate_jsonl_file

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TAQRIB_PDF = _REPO_ROOT / "datasets" / "unparsed" / "kitab_turats" / "taqrib" / "taqrib.pdf"


class TestTaqribParser(unittest.TestCase):
    def test_tounicode_cmap_contains_ligatures_and_harakat(self) -> None:
        cmap = build_taqrib_tounicode_cmap().decode("ascii")
        self.assertIn("<0bcc><0647064406440627>", cmap)  # الله reversed for RTL
        self.assertIn("<037f><064706440644>", cmap)      # لله reversed for RTL
        self.assertIn("<03f7><06230644>", cmap)          # لأ reversed for RTL
        self.assertIn("<03fb><06270644>", cmap)          # لا reversed for RTL
        self.assertIn("<02f4><064e>", cmap)              # Fatha

    def test_fix_rtl_indonesian_paragraphs_reorders_right_aligned_spans(self) -> None:
        vlines = [
            _VisualLine(
                page=66,
                oy=250,
                kind="ID",
                text="Muhson Hadnya 100 Zina",
                bold=False,
                x0=123.4,
                x1=540.3,
                spans=[
                    {"text": "Muhson Hadnya 100 ", "bbox": (123.4, 240.0, 510.9, 251.0)},
                    {"text": "Zina", "bbox": (514.5, 240.0, 540.3, 251.0)},
                ],
            ),
            _VisualLine(
                page=66,
                oy=265,
                kind="ID",
                text="dan diusir cambukan",
                bold=False,
                x0=169.3,
                x1=540.2,
                spans=[
                    {"text": "dan diusir", "bbox": (169.3, 256.0, 479.1, 267.0)},
                    {"text": "cambukan", "bbox": (482.7, 256.0, 540.2, 267.0)},
                ],
            ),
        ]
        _fix_rtl_indonesian_paragraphs(vlines)
        self.assertEqual(vlines[0].text, "Zina Muhson Hadnya 100")
        self.assertEqual(vlines[1].text, "cambukan dan diusir")

    def test_split_id_segment_extracts_footnotes_and_trailing_heading(self) -> None:
        lines = [
            _VisualLine(page=18, oy=190, kind="ID", text="Boleh mengqashar[1]", bold=False, x0=72.0, x1=300.0),
            _VisualLine(page=18, oy=410, kind="ID", text="-----------", bold=False, x0=72.0, x1=150.0),
            _VisualLine(page=18, oy=430, kind="ID", text="[1] 16 farsakh kira-kira 81 km.", bold=False, x0=72.0, x1=320.0),
            _VisualLine(page=18, oy=555, kind="ID", text="SHALAT JUM'AT", bold=True, x0=72.0, x1=210.0),
        ]
        body, footnotes, trailing = _split_id_segment(lines)
        self.assertEqual(body, "Boleh mengqashar[1]")
        self.assertEqual(footnotes, ["[1] 16 farsakh kira-kira 81 km."])
        self.assertEqual(trailing, "Shalat Jum'at")

    def test_split_id_segment_does_not_swallow_bold_titlecase_translation(self) -> None:
        lines = [
            _VisualLine(
                page=52,
                oy=305,
                kind="ID",
                text="Tidak Sah Nikah Kecuali Dengan Kehadiran Seorang Wali",
                bold=True,
                x0=72.0,
                x1=525.0,
            ),
            _VisualLine(
                page=52,
                oy=320,
                kind="ID",
                text="Dua Saksi Yang Adil",
                bold=True,
                x0=72.0,
                x1=196.8,
            ),
        ]
        body, footnotes, trailing = _split_id_segment(lines)
        self.assertIn("Tidak Sah Nikah", body)
        self.assertEqual(footnotes, [])
        self.assertIsNone(trailing)

    def test_format_heading_title_normalizes_case_and_parens(self) -> None:
        self.assertEqual(_format_heading_title("NIKAH AMAT ( BUDAK PEREMPUAN )"), "Nikah Amat (Budak Perempuan)")
        self.assertEqual(_format_heading_title('"Fasal"'), "Fasal")

    @unittest.skipUnless(_TAQRIB_PDF.exists(), "taqrib.pdf not present in local datasets/")
    def test_parse_full_taqrib_pdf_produces_validated_corpus(self) -> None:
        parser = TaqribParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "taqrib.jsonl"
            count = parser.export_jsonl(_TAQRIB_PDF, out_path, validate=True)
            self.assertEqual(count, 138)
            total, errors = validate_jsonl_file(out_path)
            self.assertEqual(total, 138)
            self.assertEqual(errors, [])

        records = list(parser.parse(_TAQRIB_PDF))
        # All 17 top-level divisions (Muqaddimah + 16 Kitabs)
        kitab_levels = list(dict.fromkeys(r["hierarchy"][1] for r in records))
        self.assertEqual(len(kitab_levels), 17)
        # Ligatures decoded accurately
        muq = records[0]["content"]["arabic_raw"]
        self.assertIn("بسم الله الرحمن الرحيم الحمد لله رب العالمين", muq)
        self.assertIn("النبي الأمي", muq)
        self.assertIn("مذهب الإمام الشافعي", muq)
        # Duplicated Kitab Shalat (p.9-11) dropped, keeping clean p.12-13 copy
        shalat_c001 = next(r for r in records if r["doc_id"] == "turats_matan_al_ghayah_wat_taqrib_k03")
        self.assertEqual(shalat_c001["metadata"]["pdf_pages"], [12])
        # RTL Indonesian paragraphs on p.66 & p.69 reconstructed cleanly
        hudud_c001 = next(r for r in records if r["doc_id"] == "turats_matan_al_ghayah_wat_taqrib_k11")
        self.assertIn("Zina Muhson Hadnya Di ranjam", hudud_c001["content"]["indonesian"])
        # No empty indonesian or arabic_raw
        for rec in records:
            self.assertTrue(rec["content"]["arabic_raw"].strip())
            self.assertTrue(rec["content"]["indonesian"].strip())
