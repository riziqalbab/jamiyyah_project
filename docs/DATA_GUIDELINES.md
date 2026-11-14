# Data Guidelines

Pedoman kurasi, normalisasi, dan validasi dataset Jamiyyah Project.

## 1. Canonical Format

Seluruh dataset terstruktur wajib berbentuk `.jsonl` dan lolos validasi `packages/schema` (`jamiyyah_schema.validate` atau `@jamiyyah/schema`).

## 2. Arabic Normalization (`packages/normalizer`)

- `content.arabic_raw` **wajib** mempertahankan teks asli tanpa modifikasi harakat/karakter.
- `content.arabic_clean` digunakan untuk indexing pencarian dengan:
  - Penghapusan harakat dan *tatweel*.
  - Unifikasi Alif (`أ`, `إ`, `آ`, `ٱ` -> `ا`) dan Ya (`ى`, `ی` -> `ي`).

## 3. Semantic Chunking

- Potong berdasarkan kesatuan pembahasan (satu hadits, satu kasus Bahtsul Masail, satu fasal/mas'alah).
- Sertakan `hierarchy` lengkap pada setiap chunk dan bangun `content.embedding_text` menggunakan `build_embedding_text`.
- Pisahkan catatan kaki ke `metadata.footnotes`.

## 4. Verification Workflow

1. `pending`: Baru diekstrak dari sumber mentah.
2. `machine_verified`: Lolos validasi skema, encoding, dan kelengkapan metadata.
3. `scholarly_verified`: Telah ditashih oleh reviewer keilmuan yang kompeten.
4. `rejected`: Tidak memenuhi standar kualitas atau validitas sumber.
