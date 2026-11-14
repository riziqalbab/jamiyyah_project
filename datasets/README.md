# Jamiyyah Datasets

Direktori ini menyimpan data literatur Islam yang diproses oleh pipeline Jamiyyah.

## Struktur Folder

- `samples/` — Contoh kecil dataset `.jsonl` sesuai Canonical Schema untuk pengujian, validasi CI, dan referensi kontributor (**di-track di Git**).
- `unparsed/` — Sumber data mentah seperti `.csv`, `.bok`/SQLite Shamela, PDF, atau hasil scraping (**di-gitignore**, disimpan di storage eksternal seperti Hugging Face Hub private atau Object Storage).
- `parsed/` — Hasil konversi lengkap dalam format `.jsonl` (**di-gitignore**, didistribusikan melalui Hugging Face Hub / Object Storage sesuai status hak cipta masing-masing sumber).

## Validasi Sample

```bash
PYTHONPATH=packages/schema python3 -m jamiyyah_schema datasets/samples/canonical_sample.jsonl
```

## Ketentuan Hak Cipta

Pastikan setiap sumber dataset yang ditambahkan ke `unparsed/` maupun `parsed/` memiliki kejelasan asal-usul, atribusi, dan izin distribusi sesuai ketentuan penerbit, lembaga, atau pemegang hak cipta terkait.
