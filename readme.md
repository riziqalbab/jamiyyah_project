# Jamiyyah Project

> **Open-Source Islamic Knowledge Retrieval Engine with Strict Grounding & Verifiable Scholarly References**

**Jamiyyah Project** adalah inisiatif *open-source* untuk membangun mesin pencarian dan tanya-jawab literatur Islam berbasis Artificial Intelligence (AI) dengan pendekatan **Closed-Book Retrieval-Augmented Generation (RAG)**.

Jamiyyah dirancang untuk membantu pengguna menelusuri, memahami, dan mengakses literatur Islam, meliputi Fiqih, Ushul Fiqih, Qawaid Fiqhiyyah, Akidah, Hadits, Tafsir, Fatwa, dan hasil Bahtsul Masail.

Berbeda dengan chatbot AI umum yang mengandalkan pengetahuan internal model (*parametric memory*) dan berpotensi menghasilkan informasi atau referensi yang tidak valid, Jamiyyah menerapkan pendekatan **Strict Grounding** — yaitu membatasi proses generasi jawaban hanya berdasarkan dokumen referensi yang ditemukan dalam database terkurasi. Setiap klaim informatif wajib memiliki referensi yang dapat ditelusuri berupa kutipan teks asli (*'ibarat kitab* atau *matan hadits*) beserta metadata sumbernya.

> **Disclaimer:** Jamiyyah tidak dimaksudkan untuk menggantikan ulama, proses ijtihad, maupun otoritas keagamaan. Sistem ini berfungsi sebagai alat bantu pencarian, dokumentasi, dan eksplorasi literatur Islam.

---

## Daftar Isi

- [1. Core Principles](#1-core-principles)
- [2. System Architecture](#2-system-architecture)
- [3. Jamiyyah Canonical Schema](#3-jamiyyah-canonical-schema)
- [4. Fine-Tuning Strategy](#4-fine-tuning-strategy)
- [5. Technology Stack](#5-technology-stack)
- [6. Repository & Dataset Structure](#6-repository--dataset-structure)
- [7. Evaluation & Benchmarking](#7-evaluation--benchmarking)
- [8. Contribution Guidelines](#8-contribution-guidelines)
- [9. License & Copyright](#9-license--copyright)
- [10. Project Vision](#10-project-vision)

---

## 1. Core Principles

Jamiyyah dibangun berdasarkan lima prinsip utama:

### 1.1 Strict Grounding & Hallucination Mitigation

Sistem dirancang untuk meminimalkan halusinasi melalui pembatasan konteks LLM. LLM tidak diperbolehkan menggunakan pengetahuan eksternal untuk melengkapi jawaban atau mengarang referensi yang tidak ditemukan dalam database.

Peran LLM dibatasi pada:
- Merangkum informasi dari dokumen yang ditemukan.
- Menerjemahkan teks Arab ke Bahasa Indonesia.
- Menjelaskan konteks berdasarkan referensi yang tersedia.
- Mengorganisasi kutipan dan daftar pustaka.
- Menyajikan perbedaan pendapat apabila didukung oleh sumber.

Sistem tidak boleh mengklaim bahwa suatu pendapat merupakan satu-satunya pendapat dalam Mazhab apabila referensi yang tersedia tidak mendukung kesimpulan tersebut.

### 1.2 Strict Abstention (*Tawaqquf*)

Jamiyyah menerapkan prinsip *tawaqquf* ketika referensi tidak mencukupi. Sistem wajib menolak memberikan kesimpulan apabila:
- Tidak ditemukan referensi yang relevan.
- Skor relevansi hasil retrieval berada di bawah ambang batas.
- Dokumen tidak memiliki sumber yang dapat diverifikasi.
- Konteks yang ditemukan tidak cukup untuk menjawab pertanyaan.
- Terdapat konflik referensi yang belum dapat dijelaskan secara memadai.

Sistem tidak boleh memaksakan jawaban berdasarkan pengetahuan internal model.

### 1.3 Verifiable Citation (*Sanad Rujukan*)

Setiap informasi yang disajikan harus memiliki referensi yang dapat ditelusuri. Metadata referensi mencakup:
- Nama kitab atau dokumen.
- Nama pengarang atau penyusun.
- Juz dan halaman.
- Bab, fasal, atau mas'alah.
- Sumber penerbitan.
- Forum dan tahun keputusan Bahtsul Masail apabila relevan.
- URL sumber apabila tersedia.

Setiap citation ID wajib divalidasi terhadap database sebelum jawaban ditampilkan.

> *Catatan: Istilah "sanad rujukan" dalam proyek ini merujuk pada rantai penelusuran sumber literatur, bukan klaim bahwa sistem telah memverifikasi sanad periwayatan hadits secara ilmiah.*

### 1.4 Scholarly Verification

Validitas teknis sebuah kutipan tidak otomatis menjamin kebenaran interpretasi keagamaannya. Karena itu, Jamiyyah membedakan dua proses validasi:

- **Technical Validation:** Memastikan teks, metadata, halaman, identitas dokumen, dan citation ID sesuai dengan sumber yang tersimpan.
- **Scholarly Validation:** Memastikan ketepatan pembacaan, konteks, terjemahan, atribusi pendapat, dan interpretasi melalui kurasi ahli atau pemeriksa yang kompeten.

Dataset yang belum melalui proses pentashihan harus memiliki status verifikasi yang jelas.

### 1.5 Unified Corpus Standardization

Seluruh sumber literatur distandarisasi ke dalam satu skema JSON kanonik. Standarisasi ini memungkinkan berbagai jenis dokumen diproses menggunakan pipeline yang sama untuk kebutuhan:
- Parsing & normalisasi.
- Chunking & embedding.
- Indexing & retrieval.
- Citation generation & evaluation.

---

## 2. System Architecture

Arsitektur Jamiyyah terdiri dari dua komponen utama:
1. **Data Ingestion & Standardization Pipeline**
2. **Multi-Layered RAG Runtime**

### 2.1 Data Ingestion & Standardization Pipeline

Pipeline ini bertanggung jawab mengubah sumber literatur mentah menjadi dataset terstruktur.

#### Raw Sources
Sumber data yang direncanakan meliputi:
- Maktabah Shamela (`.bok` / SQLite)
- Dataset JSON Hadits 9 Imam
- NU Online
- LBM PWNU
- FMPP
- Ahkamul Fuqaha
- Literatur Kitab Turats
- Dokumen Fatwa dan Tafsir

Setiap sumber harus memiliki informasi asal-usul dan ketentuan penggunaan yang jelas.

#### Parser & Extractor
Mengekstrak teks mentah beserta struktur dokumen, meliputi:
- Matan, Syarah, dan catatan kaki (*tahqiq*).
- Struktur kitab, bab, fasal, dan mas'alah.
- Metadata bibliografi.

#### Arabic Normalizer
Menyediakan dua representasi teks Arab:
- **`arabic_raw`**: Teks asli lengkap dengan harakat untuk kebutuhan tampilan dan kutipan.
- **`arabic_clean`**: Teks yang dinormalisasi untuk kebutuhan pencarian (menghilangkan harakat, menghilangkan *tatweel*, unifikasi karakter Alif dan Ya, serta mempertahankan hubungan dengan teks asli).

Normalisasi tidak boleh mengubah atau menimpa teks sumber.

#### Semantic & Structural Chunker
Memotong dokumen berdasarkan kesatuan pembahasan, bukan berdasarkan jumlah karakter tetap secara buta. Contoh unit chunk:
- Satu Hadits utuh.
- Satu kasus Tanya-Jawab Bahtsul Masail.
- Satu Fasl atau Mas'alah dalam kitab kuning.

Setiap chunk wajib menyertakan hierarki dokumen agar konteks tetap terjaga. Apabila satu pembahasan terlalu panjang, sistem diperbolehkan melakukan pemecahan lanjutan dengan mempertahankan relasi antar-chunk.

#### Schema Validator
Memvalidasi dataset menggunakan **Pydantic** atau **Zod** sebelum disimpan ke dalam format `.jsonl`. Validasi mencakup struktur data, tipe field, enum, identitas dokumen, dan kelengkapan metadata wajib.

#### Multilingual Embedding & Indexing
Mengubah teks menjadi representasi vektor menggunakan model multilingual seperti `BAAI/bge-m3`, lalu mengindeksnya dengan **Hybrid Search**:
- Dense Vector Search.
- Sparse Retrieval / BM25.

### 2.2 Multi-Layered RAG Runtime

RAG Runtime memproses pertanyaan pengguna hingga menghasilkan jawaban berbasis referensi.

#### Query Expansion & Cross-Lingual Translation
Memperluas pertanyaan Bahasa Indonesia menjadi istilah pencarian yang relevan dalam Bahasa Arab.

Contoh pertanyaan: *"Bagaimana hukum jual beli dengan sistem cicilan?"*
- البيع بالتقسيط
- بيع النسيئة
- شروط البيع
- الأجل في البيع

Ekspansi berfungsi untuk memperluas pencarian, bukan menetapkan kesimpulan hukum.

#### Hybrid Search (Dense + BM25)
Menggabungkan dua metode pencarian:
- **Dense Vector Search:** Memahami kesamaan semantik dan konteks.
- **Sparse Retrieval / BM25:** Menangkap kata kunci eksak, istilah teknis Fiqih, serta potongan *'ibarat*.

Hasil keduanya digabungkan menggunakan metode fusion seperti **Reciprocal Rank Fusion (RRF)**.

#### Cross-Encoder Reranker
Menyaring ulang hasil pencarian menggunakan `BAAI/bge-reranker-v2-m3` untuk memperoleh dokumen yang paling relevan terhadap pertanyaan pengguna. Skor reranker digunakan sebagai indikator relevansi, bukan sebagai probabilitas kebenaran hukum.

### 2.3 Three-Layer Guardrails

#### Layer 1: Retrieval Quality Gate
Sebelum memanggil LLM, sistem mengevaluasi kualitas dokumen hasil retrieval. Aturan awal:
- Skor reranker di bawah `0.65` menyebabkan proses dihentikan.
- Dokumen yang tidak memiliki provenance valid tidak boleh digunakan.
- Konteks yang tidak cukup untuk menjawab pertanyaan menyebabkan *abstention*.
- LLM tidak dipanggil apabila retrieval gagal memenuhi kriteria.

> *Catatan: Threshold `0.65` merupakan konfigurasi awal yang wajib dikalibrasi menggunakan dataset benchmark, dan tidak boleh dianggap sebagai standar universal karena skor dapat berbeda berdasarkan model dan konfigurasi.*

#### Layer 2: Strict Grounded Generation
Jika konteks memenuhi persyaratan, sistem memanggil LLM dengan konfigurasi:
- `temperature: 0.0`
- Strict context grounding (tanpa pengetahuan eksternal).
- No fabricated citations & no unsupported legal conclusions.
- Mandatory citation ID: `[ID: <chunk_id>]`.

Sistem harus membedakan antara:
1. Pendapat yang secara eksplisit dinyatakan dalam referensi.
2. Penjelasan atau parafrasa dari referensi.
3. Informasi yang tidak ditemukan dalam referensi.

Apabila pengguna meminta penetapan hukum yang membutuhkan proses *istinbath*, sistem tidak boleh mengklaim telah melakukan *istinbath* secara mandiri.

#### Layer 3: Citation & Entailment Validation
Sebelum jawaban ditampilkan, sistem melakukan dua jenis validasi:

- **Citation Validation:** Memastikan seluruh `chunk_id` tersedia, dokumen sumber valid, metadata bibliografi sesuai, kutipan berasal dari teks tersimpan, dan daftar pustaka dirender langsung dari database.
- **Claim Entailment Validation:** Memeriksa apakah setiap klaim didukung referensi, memiliki konteks yang sesuai, mendeteksi klaim yang terlalu jauh atau kontradiksi antar-referensi, dan menolak klaim tanpa dukungan memadai.

> *Validator otomatis tidak dianggap sebagai pengganti pemeriksaan ahli. Jika validasi gagal, sistem harus menghapus klaim yang tidak didukung atau menolak menampilkan jawaban.*

---

## 3. Jamiyyah Canonical Schema

Seluruh dataset terstruktur wajib menggunakan format `.jsonl` (JSON Lines) dengan skema standar berikut.

### 3.1 Example Dataset Record

```json
{
  "chunk_id": "bm_pwnu_jatim_2023_012_c01",
  "doc_id": "bm_pwnu_jatim_2023_012",
  "source_category": "bahtsul_masail",
  "language": "mixed",
  "hierarchy": [
    "Bahtsul Masail PWNU Jawa Timur",
    "Muamalah",
    "Hukum Transaksi Paylater"
  ],
  "content": {
    "arabic_raw": "وَكُلُّ قَرْضٍ جَرَّ مَنْفَعَةً فَهُوَ رِبًا...",
    "arabic_clean": "وكل قرض جر منفعة فهو ربا...",
    "indonesian": "Contoh terjemahan atau penjelasan dari sumber...",
    "embedding_text": "Kategori: Bahtsul Masail | Hierarki: Bahtsul Masail PWNU Jawa Timur > Muamalah > Hukum Transaksi Paylater | Konteks: ... | Ibarat: ..."
  },
  "citation": {
    "short_label": "BM PWNU Jatim (2023) - Hasyiyah Al-Bajuri (1/365)",
    "full_reference": "Referensi keputusan dan kitab yang digunakan...",
    "url": "https://nu.or.id/bahtsul-masail/..."
  },
  "metadata": {
    "forum": "LBM PWNU Jawa Timur",
    "year": 2023,
    "madzhab": "Syafi'i",
    "verification_status": "pending",
    "footnotes": [],
    "referenced_books": [
      {
        "title": "Hasyiyah Al-Bajuri",
        "author": "Ibrahim Al-Bajuri",
        "juz": 1,
        "page": 365
      }
    ]
  }
}
```

> *Catatan: Contoh di atas hanya ilustrasi struktur data. Isi kutipan, atribusi, dan referensi hukum harus diverifikasi sebelum digunakan sebagai dataset.*

### 3.2 Field Standardization

| Field | Description |
|---|---|
| `chunk_id` | ID unik setiap chunk. |
| `doc_id` | ID unik dokumen sumber. |
| `source_category` | Kategori sumber literatur. |
| `language` | Bahasa konten (`ar`, `id`, `mixed`). |
| `hierarchy` | Struktur kitab, bab, dan pembahasan. |
| `content.arabic_raw` | Teks Arab asli lengkap dengan harakat. |
| `content.arabic_clean` | Teks Arab hasil normalisasi untuk pencarian. |
| `content.indonesian` | Terjemahan atau penjelasan Bahasa Indonesia. |
| `content.embedding_text` | Teks gabungan terstruktur yang digunakan untuk embedding. |
| `citation` | Referensi bibliografi (`short_label`, `full_reference`, `url`). |
| `metadata` | Metadata tambahan, referensi kitab, dan status verifikasi. |

### 3.3 Enumerations

**Source Category**

```typescript
type SourceCategory =
  | "bahtsul_masail"
  | "kitab_turats"
  | "hadith"
  | "quran_tafsir"
  | "fatwa"
  | "qawaid_fiqh";
```

**Verification Status**

```typescript
type VerificationStatus =
  | "pending"
  | "machine_verified"
  | "scholarly_verified"
  | "rejected";
```

- `pending`: Belum melalui proses verifikasi.
- `machine_verified`: Telah lolos validasi teknis otomatis.
- `scholarly_verified`: Telah diperiksa oleh reviewer yang kompeten.
- `rejected`: Tidak memenuhi standar kualitas dataset.

> *Validasi mesin tidak boleh disamakan dengan validasi keilmuan.*

### 3.4 Arabic Normalization Rules

- **`arabic_raw`**: Harus mempertahankan teks asli tanpa modifikasi.
- **`arabic_clean`**: Digunakan untuk indexing dengan aturan:
  - Menghilangkan harakat.
  - Menghilangkan *tatweel*.
  - Unifikasi karakter Alif.
  - Unifikasi karakter Ya.
  - Mempertahankan hubungan dengan teks asli.

### 3.5 Embedding Text Construction

Field `content.embedding_text` wajib menyertakan hierarki pembahasan:

```text
Kategori: Kitab Turats

Hierarki:
Fathul Mu'in > Kitab Shalat > Bab Syarat Shalat

Konteks:
Pembahasan mengenai syarat sah pelaksanaan shalat.

Ibarat:
[Original Arabic Text]
```

### 3.6 Semantic Chunking Rules

- Tidak menggunakan pemotongan karakter secara buta.
- Mempertahankan satu kesatuan pembahasan.
- Menyertakan hierarki pada setiap chunk.
- Memisahkan catatan kaki ke `metadata.footnotes`.
- Mempertahankan relasi matan dan syarah.
- Mempertahankan relasi antar-chunk jika satu pembahasan terlalu panjang.

---

## 4. Fine-Tuning Strategy

Fine-tuning **bukan** digunakan untuk memasukkan hafalan kitab ke dalam memori model, melainkan untuk meningkatkan kemampuan model dalam memahami istilah, mengikuti instruksi, dan melakukan *grounding*.

### 4.1 Strict Grounding & Abstention Training
Melatih model menggunakan pasangan contoh positif dan negatif dengan fokus:
- Menolak pertanyaan tanpa referensi.
- Menghindari pengetahuan eksternal.
- Membedakan konteks relevan dan tidak relevan.
- Mengikuti aturan sitasi.
- Mengidentifikasi informasi yang tidak tersedia.

### 4.2 Domain Adaptation: Turats Terminology
Meningkatkan pemahaman model terhadap terminologi Fiqih, Ushul Fiqih, Qawaid Fiqhiyyah, Mushthalah Hadits, dan istilah klasik dalam Kitab Turats.

### 4.3 Consistent Answer Formatting
Membakukan format jawaban:
1. Ringkasan jawaban berdasarkan referensi.
2. Uraian pembahasan.
3. Kutipan *'ibarat*.
4. Referensi dan metadata.
5. Catatan keterbatasan jika terdapat perbedaan pendapat atau kekurangan sumber.

Format ini tidak boleh mendorong model menciptakan putusan hukum baru.

### 4.4 Embedding & Reranker Fine-Tuning
Melatih model menggunakan pasangan *(Pertanyaan Bahasa Indonesia, Referensi Bahasa Arab, Label Relevansi, Konteks Pembahasan)* untuk meningkatkan kualitas retrieval lintas bahasa.

---

## 5. Technology Stack

| Component | Technology |
|---|---|
| Data Processing | Python |
| Document Parsing | PyMuPDF, BeautifulSoup4 |
| Arabic Processing | PyArabic |
| Schema Validation | Pydantic, Zod |
| Data Format | JSONL |
| Dataset Hosting | Hugging Face Hub (`datasets`) |
| Database | PostgreSQL |
| Vector Search | pgvector / Qdrant |
| Sparse Search | pg_search / BM25 |
| Embedding | `BAAI/bge-m3` |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Backend | NestJS / Next.js |
| Worker Service | Python |
| LLM | OpenAI / Anthropic / Self-hosted Models |

### LLM Compatibility

Jamiyyah dirancang agar agnostik terhadap penyedia LLM (OpenAI GPT-4o, Anthropic Claude, Qwen, maupun model *open-weight* lainnya yang kompatibel). Pemilihan model mempertimbangkan kualitas grounding, kemampuan multilingual, biaya inference, dan kebutuhan infrastruktur.

---

## 6. Repository & Dataset Structure

```text
jamiyyah_project/
├── packages/
│   ├── schema/              # Pydantic & Zod canonical schemas + JSONL validator
│   ├── normalizer/          # Arabic normalization & embedding_text builder
│   ├── parsers/             # Hadith CSV, Shamela, Bahtsul Masail parsers
│   └── rag-engine/          # Hybrid RRF fusion & Three-Layer Guardrails
├── apps/
│   ├── api/                 # REST / tRPC API (planned)
│   └── web/                 # Q&A Interface & Reference Explorer (planned)
├── code/
│   └── parsing/             # Notebook & eksperimen parsing
├── datasets/
│   ├── samples/             # Sample JSONL datasets (tracked in Git)
│   ├── unparsed/            # Raw sources (git-ignored / external storage)
│   ├── parsed/              # Processed JSONL (git-ignored / external storage)
│   └── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_GUIDELINES.md
│   └── EVALUATION.md
├── .env.example
├── .gitignore
├── LICENSE
├── package.json
├── pyproject.toml
└── readme.md
```

> **Kebijakan Penyimpanan Dataset:** File dataset mentah dan hasil parsing berukuran besar (`datasets/unparsed/` dan `datasets/parsed/`) **tidak** disimpan di GitHub karena batas ukuran file/LFS serta pertimbangan hak cipta literatur. Hanya sample kecil (`datasets/samples/`) yang di-track di Git untuk keperluan pengujian dan kontribusi.

### Dataset Distribution (Hugging Face Hub)

Distribusi dataset penuh (`datasets/parsed/` dan opsional backup private `datasets/unparsed/`) dikelola melalui **Hugging Face Hub** agar tidak terkena batas ukuran file GitHub sekaligus terintegrasi langsung dengan pipeline Python (`datasets` / `huggingface_hub`).

- **Repo Parsed (`jamiyyah-corpus`):** Menyimpan file `.jsonl` sesuai Canonical Schema (disarankan **Private** selama status kurasi masih `pending` atau izin distribusi sumber masih diverifikasi).
- **Repo Raw (`jamiyyah-raw`, Private):** Backup sumber mentah (`unparsed/`) seperti `.csv`, `.bok`, atau PDF.

**Install CLI & Login:**

```bash
pip install -U huggingface_hub
hf auth login
```

**Upload Dataset:**

```bash
# Upload hasil parsing JSONL ke Hugging Face Dataset Hub
hf upload <username>/jamiyyah-corpus datasets/parsed/ parsed/ \
  --repo-type dataset \
  --exclude ".gitkeep" --exclude ".DS_Store"
```

**Download Dataset:**

```bash
# Tarik dataset ke folder lokal datasets/
hf download <username>/jamiyyah-corpus \
  --repo-type dataset \
  --local-dir datasets/
```

**Load Langsung di Python:**

```python
from datasets import load_dataset

ds = load_dataset("<username>/jamiyyah-corpus", data_files="parsed/hadist/hadits.jsonl")
```

---

## 7. Evaluation & Benchmarking

Keandalan Jamiyyah diukur menggunakan benchmark yang dapat direproduksi dengan metrik utama:

| Metric | Evaluation Purpose |
|---|---|
| `Recall@K` | Mengukur kemampuan menemukan referensi relevan. |
| `MRR` | Mengukur posisi dokumen relevan dalam hasil pencarian. |
| `NDCG@K` | Mengukur kualitas ranking hasil retrieval. |
| `Citation Precision` | Mengukur validitas referensi yang digunakan. |
| `Citation Coverage` | Mengukur proporsi klaim yang memiliki referensi. |
| `Faithfulness` | Mengukur kesesuaian jawaban dengan konteks. |
| `Abstention Precision` | Mengukur ketepatan sistem dalam menolak jawaban. |
| `Abstention Recall` | Mengukur kemampuan menolak pertanyaan yang tidak memiliki dukungan sumber. |

Benchmark harus mencakup:
- Pertanyaan dengan referensi yang tersedia.
- Pertanyaan tanpa referensi.
- Pertanyaan ambigu.
- Pertanyaan dengan beberapa pendapat.
- Pertanyaan dengan referensi yang saling bertentangan.
- Pertanyaan yang membutuhkan pengetahuan di luar cakupan database.

---

## 8. Contribution Guidelines

Jamiyyah merupakan proyek *open-source* yang terbuka bagi:
- Software Engineer & AI/ML Engineer.
- NLP Researcher.
- Santri, akademisi, peneliti Fiqih/Ushul Fiqih, dan pegiat literasi Islam & Turats.

**Area Kontribusi:**
- **Engineering:** Pengembangan parser, Arabic Normalizer, optimalisasi Hybrid Search, RAG Engine, Citation Validator, serta API dan Web Interface.
- **AI & Research:** Eksperimen embedding multilingual, fine-tuning reranker, benchmark anti-halusinasi, evaluasi entailment, dan pengembangan mekanisme abstention.
- **Islamic Literature & Data:** Penambahan dataset Kitab Turats & Bahtsul Masail, kurasi dan pentashihan teks, validasi kutipan/referensi, serta penyusunan benchmark pertanyaan hukum Islam.

Setiap kontribusi dataset wajib mengikuti Canonical Schema dan Data Guidelines.

---

## 9. License & Copyright

Kode sumber Jamiyyah Project menggunakan **MIT License**.

Namun, lisensi perangkat lunak tidak secara otomatis memberikan hak untuk mendistribusikan seluruh literatur yang digunakan sebagai dataset. Hak cipta dan ketentuan penggunaan atas Kitab Turats, terjemahan, dataset Hadits, kompilasi putusan Bahtsul Masail, fatwa, dan dokumen referensi lainnya tetap mengikuti ketentuan masing-masing *mualif*, penerbit, lembaga, dan pemegang hak terkait.

Setiap kontributor bertanggung jawab memastikan sumber data yang ditambahkan memiliki dasar penggunaan dan distribusi yang sesuai.

---

## 10. Project Vision

Jamiyyah Project memiliki visi membangun ekosistem pengetahuan Islam berbasis teknologi AI yang transparan, terstruktur, dan dapat diverifikasi. AI bukan pengganti ulama, bukan pengganti proses ijtihad, dan bukan otoritas dalam menetapkan hukum Islam.

AI dalam Jamiyyah berperan sebagai alat bantu untuk:
- Menemukan literatur dan menelusuri referensi.
- Memahami konteks pembahasan dan menerjemahkan teks.
- Membandingkan pendapat berdasarkan sumber.
- Menyajikan informasi dengan referensi yang dapat diverifikasi.

Ketika referensi tidak tersedia, sistem harus berani mengatakan tidak tahu.

**No Reference, No Answer.**

---

<p align="center">
  <strong>Jamiyyah Project</strong><br />
  Open Knowledge. Verifiable References. Responsible AI.
</p>
