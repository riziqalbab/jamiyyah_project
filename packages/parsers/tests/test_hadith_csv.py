import json
import tempfile
import unittest
from pathlib import Path

from jamiyyah_parsers import HadithCsvParser
from jamiyyah_schema import validate_jsonl_file


class TestHadithCsvParser(unittest.TestCase):
    def test_parses_and_validates_hadith_csv(self) -> None:
        csv_content = (
            "Perawi,Arab,Terjemahan\n"
            '"Hadits Abu Daud Nomor 1","حَدَّثَنَا عَبْدُ اللَّهِ","Telah menceritakan kepada kami Abdullah."\n'
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            input_csv = tmp / "hadits.csv"
            output_jsonl = tmp / "hadith.jsonl"
            input_csv.write_text(csv_content, encoding="utf-8")

            count = HadithCsvParser().export_jsonl(input_csv, output_jsonl)
            self.assertEqual(count, 1)

            validated_count, errors = validate_jsonl_file(output_jsonl)
            self.assertEqual(validated_count, 1)
            self.assertEqual(errors, [])

            record = json.loads(output_jsonl.read_text(encoding="utf-8").strip())
            self.assertEqual(record["chunk_id"], "hadith_abu_daud_1_c01")
            self.assertEqual(record["source_category"], "hadith")
            self.assertEqual(record["content"]["arabic_clean"], "حدثنا عبد الله")
            self.assertEqual(record["metadata"]["verification_status"], "pending")


if __name__ == "__main__":
    unittest.main()
