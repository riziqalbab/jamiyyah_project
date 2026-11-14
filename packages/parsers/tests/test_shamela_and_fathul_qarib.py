import tempfile
import unittest
from pathlib import Path

import pymupdf
from jamiyyah_parsers.fathul_qarib import (
    FathulQaribParser,
    PdfBook,
    PdfKitab,
    PdfUnit,
    align_fathul_qarib,
    clean_indonesian_text,
)
from jamiyyah_parsers.shamela import (
    ShamelaBook,
    ShamelaKitab,
    ShamelaParagraph,
    ShamelaParser,
    ShamelaSection,
    extract_shamela_book,
)
from jamiyyah_schema.validate import validate_jsonl_file


def _write_shamela_fixture(root: Path) -> Path:
    pages = root / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    nav = (
        '<div class="s-nav">'
        '<a href="https://shamela.ws/book/999/1">مقدمة</a>'
        '<a href="https://shamela.ws/book/999/2">كتاب الطهارة</a>'
        "</div>"
    )
    (pages / "1.html").write_text(
        f"<html><body>{nav}"
        '<div class="nass" data-page-id="1" data-page-num="10">'
        '<p><span class="anchor" id="p1"></span>بسم الله الرحمن الرحيم<a class="btn_tag" href="#p1">c</a></p>'
        '<p><span class="anchor" id="p2"></span><span class="c4">[مقدمة]</span></p>'
        '<p><span class="anchor" id="p3"></span>الحمد لله رب العالمين</p>'
        "</div></body></html>",
        encoding="utf-8",
    )
    (pages / "2.html").write_text(
        f"<html><body>{nav}"
        '<div class="nass" data-page-id="2" data-page-num="11">'
        '<p><span class="anchor" id="p1"></span><span class="c4">[كتاب الطهارة]</span></p>'
        '<p><span class="anchor" id="p2"></span>والطهارة لغة النظافة ثم '
        '<span class="c2">(المياه)</span> التي يجوز</p>'
        "</div></body></html>",
        encoding="utf-8",
    )
    (pages / "3.html").write_text(
        f"<html><body>{nav}"
        '<div class="nass" data-page-id="3" data-page-num="12">'
        '<p><span class="anchor" id="p1"></span>التطهير بها سبع مياه.</p>'
        "</div></body></html>",
        encoding="utf-8",
    )
    return root


class TestShamelaAndFathulQarib(unittest.TestCase):
    def test_clean_indonesian_text_normalizes_smart_quotes(self) -> None:
        self.assertEqual(
            clean_indonesian_text("Al „Alim As Syafi‟i ‚Kitab‛  baru"),
            "Al 'Alim As Syafi'i 'Kitab' baru",
        )

    def test_extract_shamela_book_merges_basmalah_and_cross_page_sentence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            shamela_dir = _write_shamela_fixture(Path(tmpdir))
            book = extract_shamela_book(shamela_dir, book_id=999, book_title="Test Kitab")
            self.assertEqual(len(book.kitabs), 2)
            # Basmalah stays inside Muqaddimah instead of creating a standalone tiny section
            self.assertEqual(len(book.kitabs[0].sections), 1)
            self.assertIn("بسم الله", book.kitabs[0].sections[0].arabic_raw)
            self.assertIn("الحمد لله", book.kitabs[0].sections[0].arabic_raw)
            # Mid-sentence paragraph across page 2 -> 3 is joined into one paragraph
            thaharah_sec = book.kitabs[1].sections[0]
            self.assertEqual(len(thaharah_sec.paragraphs), 1)
            self.assertEqual(thaharah_sec.shamela_pages, [2, 3])
            self.assertEqual(thaharah_sec.matan_arabic, ["(المياه)"])

    def test_shamela_parser_exports_valid_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            shamela_dir = _write_shamela_fixture(tmp / "shamela")
            out_path = tmp / "out.jsonl"
            parser = ShamelaParser(book_id=999, book_title="Test Kitab")
            count = parser.export_jsonl(shamela_dir, out_path, validate=True)
            self.assertEqual(count, 2)
            total, errors = validate_jsonl_file(out_path)
            self.assertEqual(total, 2)
            self.assertEqual(errors, [])

    def test_align_fathul_qarib_swaps_and_attaches_footnotes(self) -> None:
        s_book = ShamelaBook(
            book_id=35120,
            title="Fathul Qarib al-Mujib",
            base_url="https://shamela.ws/book/35120",
            kitabs=[
                ShamelaKitab(
                    title="كتاب أحكام الزكاة",
                    start_page=101,
                    sections=[
                        ShamelaSection(
                            title="نصاب البقر",
                            kitab_title="كتاب أحكام الزكاة",
                            has_fasl=True,
                            paragraphs=[
                                ShamelaParagraph(
                                    text="{فصل} وأول نصاب البقر ثلاثون تبيعا.",
                                    matan=["(وأول نصاب البقر ثلاثون)"],
                                    shamela_pages=[106],
                                    kitab_pages=[106],
                                )
                            ],
                        ),
                        ShamelaSection(
                            title="نصاب الغنم",
                            kitab_title="كتاب أحكام الزكاة",
                            has_fasl=True,
                            paragraphs=[
                                ShamelaParagraph(
                                    text="{فصل} وأول نصاب الغنم أربعون شاة.",
                                    matan=["(وأول نصاب الغنم أربعون)"],
                                    shamela_pages=[107],
                                    kitab_pages=[107],
                                )
                            ],
                        ),
                    ],
                )
            ],
        )
        p_book = PdfBook(
            kitabs=[
                PdfKitab(
                    title="Kitab Hukum-hukum Zakat",
                    units=[
                        PdfUnit(
                            text="(Fasal) permulaan nishab kambing adalah empat puluh ekor[1].",
                            pages=[112],
                            heading="ZAKAT KAMBING",
                            is_bab=True,
                            is_fasal=True,
                        ),
                        PdfUnit(
                            text="(Fasal) permulaan nishab sapi adalah tiga puluh ekor.",
                            pages=[113],
                            heading="ZAKAT SAPI",
                            is_bab=True,
                            is_fasal=True,
                        ),
                    ],
                )
            ],
            footnotes_by_page={113: [("[1]", "[1] Kambing domba berusia satu tahun.")]},
        )

        aligned = align_fathul_qarib(s_book, p_book)
        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0].section_title_ar, "نصاب البقر")
        self.assertIn("sapi", aligned[0].indonesian.lower())
        self.assertEqual(aligned[0].alignment_method, "dp_swapped")
        self.assertEqual(aligned[1].section_title_ar, "نصاب الغنم")
        self.assertIn("kambing", aligned[1].indonesian.lower())
        self.assertEqual(aligned[1].footnotes, ["[1] Kambing domba berusia satu tahun."])

    def test_fathul_qarib_parser_end_to_end_with_synthetic_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            shamela_dir = _write_shamela_fixture(tmp / "shamela_999")
            pdf_path = tmp / "fathul_qarib.pdf"

            doc = pymupdf.open()
            p1 = doc.new_page(width=612, height=792)
            p1.insert_text((72, 260), "Segala puji bagi Allah Tuhan semesta alam.", fontsize=13.6)
            p2 = doc.new_page(width=612, height=792)
            p2.insert_text((72, 180), "KITAB HUKUM-HUKUM THAHARAH", fontsize=13.6, fontname="hebo")
            p2.insert_text((72, 220), "Thaharah secara bahasa berarti bersuci dan air ada tujuh.", fontsize=11.0)
            # Right-column corrupted Arabic span must be ignored
            p2.insert_text((380, 220), "mojibake_arabic_col", fontsize=11.0)
            doc.save(pdf_path)
            doc.close()

            out_path = tmp / "fq.jsonl"
            parser = FathulQaribParser(shamela_dir=shamela_dir, book_id=999)
            count = parser.export_jsonl(pdf_path, out_path, validate=True)
            self.assertEqual(count, 2)
            total, errors = validate_jsonl_file(out_path)
            self.assertEqual(total, 2)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
