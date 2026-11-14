# Jamiyyah Project

### Open-Source Islamic Knowledge Retrieval Engine with Strict Grounding & Verifiable Scholarly References

**Jamiyyah Project** adalah inisiatif open-source untuk membangun mesin pencarian dan tanya-jawab literatur Islam berbasis teknologi Artificial Intelligence (AI) dengan pendekatan **Closed-Book Retrieval-Augmented Generation (RAG)**.

Jamiyyah dirancang untuk membantu pengguna menelusuri, memahami, dan mengakses literatur Islam, meliputi Fiqih, Ushul Fiqih, Qawaid Fiqhiyyah, Akidah, Hadits, Tafsir, Fatwa, dan hasil Bahtsul Masail.

Berbeda dengan chatbot AI umum yang mengandalkan pengetahuan internal model (*parametric memory*) dan berpotensi menghasilkan informasi atau referensi yang tidak valid, Jamiyyah menerapkan pendekatan **Strict Grounding**, yaitu membatasi proses generasi jawaban berdasarkan dokumen referensi yang berhasil ditemukan dalam database terkurasi.

Setiap klaim informatif wajib memiliki referensi yang dapat ditelusuri, berupa kutipan teks asli (*'ibarat kitab* atau *matan hadits*) beserta metadata sumbernya.

**Jamiyyah tidak dimaksudkan untuk menggantikan ulama, proses ijtihad, maupun otoritas keagamaan. Sistem ini berfungsi sebagai alat bantu pencarian, dokumentasi, dan eksplorasi literatur Islam.**

---

## 1. Core Principles

Jamiyyah dibangun berdasarkan lima prinsip utama.

### 1.1 Strict Grounding & Hallucination Mitigation

Sistem dirancang untuk meminimalkan halusinasi melalui pembatasan konteks LLM.

LLM tidak diperbolehkan menggunakan pengetahuan eksternal untuk melengkapi jawaban atau mengarang referensi yang tidak ditemukan dalam database.

Peran LLM dibatasi pada:

- Merangkum informasi dari dokumen yang ditemukan.
- Menerjemahkan teks Arab ke Bahasa Indonesia.
- Menjelaskan konteks berdasarkan referensi yang tersedia.
- Mengorganisasi kutipan dan daftar pustaka.
- Menyajikan perbedaan pendapat apabila didukung oleh sumber.

Sistem tidak boleh mengklaim bahwa suatu pendapat merupakan satu-satunya pendapat dalam Mazhab apabila referensi yang tersedia tidak mendukung kesimpulan tersebut.

### 1.2 Strict Abstention (Tawaqquf)

Jamiyyah menerapkan prinsip *tawaqquf* ketika referensi tidak mencukupi.

Sistem wajib menolak memberikan kesimpulan apabila:

- Tidak ditemukan referensi yang relevan.
- Skor relevansi hasil retrieval berada di bawah ambang batas.
- Dokumen tidak memiliki sumber yang dapat diverifikasi.
- Konteks yang ditemukan tidak cukup untuk menjawab pertanyaan.
- Terdapat konflik referensi yang belum dapat dijelaskan secara memadai.

Sistem tidak boleh memaksakan jawaban berdasarkan pengetahuan internal model.

### 1.3 Verifiable Citation (Sanad Rujukan)

Setiap informasi yang disajikan harus memiliki referensi yang dapat ditelusuri.

Metadata referensi mencakup:

- Nama kitab atau dokumen.
- Nama pengarang atau penyusun.
- Juz dan halaman.
- Bab, fasal, atau mas'alah.
- Sumber penerbitan.
- Forum dan tahun keputusan Bahtsul Masail apabila relevan.
- URL sumber apabila tersedia.

Setiap citation ID wajib divalidasi terhadap database sebelum jawaban ditampilkan.

Istilah *sanad rujukan* dalam proyek ini merujuk pada rantai penelusuran sumber literatur, bukan klaim bahwa sistem telah memverifikasi sanad periwayatan hadits secara ilmiah.

### 1.4 Scholarly Verification

Validitas teknis sebuah kutipan tidak otomatis menjamin kebenaran interpretasi keagamaannya.

Karena itu, Jamiyyah membedakan dua proses validasi:

**Technical Validation**

Memastikan teks, metadata, halaman, identitas dokumen, dan citation ID sesuai dengan sumber yang tersimpan.

**Scholarly Validation**

Memastikan ketepatan pembacaan, konteks, terjemahan, atribusi pendapat, dan interpretasi melalui kurasi ahli atau pemeriksa yang kompeten.

Dataset yang belum melalui proses pentashihan harus memiliki status verifikasi yang jelas.

### 1.5 Unified Corpus Standardization

Seluruh sumber literatur distandarisasi ke dalam satu skema JSON kanonik.

Standarisasi ini memungkinkan berbagai jenis dokumen diproses menggunakan pipeline yang sama untuk kebutuhan:

- Parsing.
- Normalisasi.
- Chunking.
- Embedding.
- Indexing.
- Retrieval.
- Citation generation.
- Evaluation.

---

## 2. System Architecture

Arsitektur Jamiyyah terdiri dari dua komponen utama:

1. **Data Ingestion & Standardization Pipeline**
2. **Multi-Layered RAG Runtime**

### 2.1 Data Ingestion & Standardization Pipeline

Pipeline bertanggung jawab mengubah sumber literatur menjadi dataset terstruktur.

#### Raw Sources

Sumber data yang direncanakan meliputi:

- Maktabah Shamela (`.bok` / SQLite).
- Dataset JSON Hadits 9 Imam.
- NU Online.
- LBM PWNU.
- FMPP.
- Ahkamul Fuqaha.
- Literatur Kitab Turats.
- Dokumen Fatwa dan Tafsir.

Setiap sumber harus memiliki informasi asal-usul dan ketentuan penggunaan yang jelas.

#### Parser & Extractor

Mengekstrak teks mentah beserta struktur dokumen.

Komponen yang diidentifikasi:

- Matan.
- Syarah.
- Catatan kaki (*tahqiq*).
- Struktur kitab.
- Bab.
- Fasal.
- Mas'alah.
- Metadata bibliografi.

#### Arabic Normalizer

Menyediakan dua representasi teks Arab.

**`arabic_raw`**

Teks asli lengkap dengan harakat untuk kebutuhan tampilan dan kutipan.

**`arabic_clean`**

Teks yang dinormalisasi untuk kebutuhan pencarian:

- Menghilangkan harakat.
- Menghilangkan tatweel.
- Unifikasi karakter Alif.
- Unifikasi karakter Ya sesuai aturan normalisasi.
- Mempertahankan hubungan dengan teks asli.

Normalisasi tidak boleh mengubah atau menimpa teks sumber.

#### Semantic & Structural Chunker

Memotong dokumen berdasarkan kesatuan pembahasan, bukan berdasarkan jumlah karakter tetap secara buta.

Contoh unit chunk:

- Satu Hadits utuh.
- Satu kasus Tanya-Jawab Bahtsul Masail.
- Satu Fasl atau Mas'alah dalam kitab kuning.

Setiap chunk wajib menyertakan hierarki dokumen agar konteks tetap terjaga.

Apabila satu pembahasan terlalu panjang, sistem diperbolehkan melakukan pemecahan lanjutan dengan mempertahankan relasi antar-chunk.

#### Schema Validator

Memvalidasi dataset menggunakan Pydantic atau Zod sebelum disimpan ke dalam format `.jsonl`.

Validasi mencakup struktur data, tipe field, enum, identitas dokumen, dan kelengkapan metadata wajib.

#### Multilingual Embedding & Indexing

Mengubah teks menjadi representasi vektor menggunakan model multilingual seperti `BAAI/bge-m3`.

Hasilnya diindeks menggunakan Hybrid Search:

- Dense Vector Search.
- Sparse Retrieval / BM25.

### 2.2 Multi-Layered RAG Runtime

RAG Runtime memproses pertanyaan pengguna hingga menghasilkan jawaban berbasis referensi.

#### Query Expansion & Cross-Lingual Translation

Memperluas pertanyaan Bahasa Indonesia menjadi istilah pencarian yang relevan dalam Bahasa Arab.

Contoh:

Pertanyaan: "Bagaimana hukum jual beli dengan sistem cicilan?"

Ekspansi istilah pencarian dapat mencakup:

- البيع بالتقسيط
- بيع النسيئة
- شروط البيع
- الأجل في البيع

Ekspansi berfungsi untuk memperluas pencarian, bukan menetapkan kesimpulan hukum.

#### Hybrid Search (Dense + BM25)

Menggabungkan dua metode pencarian:

**Dense Vector Search:** Memahami kesamaan semantik dan konteks.

**Sparse Retrieval / BM25:** Menangkap kata kunci eksak, istilah teknis Fiqih, serta potongan *'ibarat*.

Hasil keduanya digabungkan menggunakan metode fusion seperti Reciprocal Rank Fusion (RRF).

#### Cross-Encoder Reranker

Menyaring ulang hasil pencarian menggunakan `BAAI/bge-reranker-v2-m3`.

Tujuannya memperoleh dokumen yang paling relevan terhadap pertanyaan pengguna.

Skor reranker digunakan sebagai indikator relevansi, bukan sebagai probabilitas kebenaran hukum.

### 2.3 Three-Layer Guardrails

Jamiyyah menggunakan tiga lapisan guardrails.

#### Layer 1: Retrieval Quality Gate

Sebelum memanggil LLM, sistem mengevaluasi kualitas dokumen hasil retrieval.

Aturan awal:

- Skor reranker di bawah `0.65` menyebabkan proses dihentikan.
- Dokumen yang tidak memiliki provenance valid tidak boleh digunakan.
- Konteks yang tidak cukup untuk menjawab pertanyaan menyebabkan abstention.
- LLM tidak dipanggil apabila retrieval gagal memenuhi kriteria.

Threshold `0.65` merupakan konfigurasi awal dan wajib dikalibrasi menggunakan dataset benchmark.

Nilai tersebut tidak boleh dianggap sebagai standar universal karena skor reranker dapat berbeda berdasarkan model dan konfigurasi.

#### Layer 2: Strict Grounded Generation

Jika konteks memenuhi persyaratan, sistem memanggil LLM menggunakan konfigurasi:

- Temperature: `0.0`.
- Strict context grounding.
- No external knowledge.
- No fabricated citations.
- No unsupported legal conclusions.
- Mandatory citation ID: `[ID: <chunk_id>]`.

LLM hanya diperbolehkan menyusun jawaban berdasarkan konteks yang diberikan.

Sistem harus membedakan antara:

- Pendapat yang secara eksplisit dinyatakan dalam referensi.
- Penjelasan atau parafrasa dari referensi.
- Informasi yang tidak ditemukan dalam referensi.

Apabila pengguna meminta penetapan hukum yang membutuhkan proses istinbath, sistem tidak boleh mengklaim telah melakukan istinbath secara mandiri.

#### Layer 3: Citation & Entailment Validation

Sebelum jawaban ditampilkan, sistem melakukan dua jenis validasi.

**Citation Validation**

- Memastikan seluruh `chunk_id` tersedia.
- Memastikan dokumen sumber valid.
- Memastikan metadata bibliografi sesuai.
- Memastikan kutipan berasal dari teks yang tersimpan.
- Merender daftar pustaka langsung dari database.

**Claim Entailment Validation**

- Memeriksa apakah setiap klaim didukung oleh referensi.
- Memeriksa apakah kutipan memiliki konteks yang sesuai.
- Mendeteksi klaim yang terlalu jauh dari isi dokumen.
- Mendeteksi kontradiksi antar-referensi.
- Menolak klaim yang tidak memiliki dukungan memadai.

Validator otomatis tidak dianggap sebagai pengganti pemeriksaan ahli.

Jika validasi gagal, sistem harus menghapus klaim yang tidak didukung atau menolak menampilkan jawaban.

---

## 3. Jamiyyah Canonical Schema

Seluruh dataset wajib menggunakan format `.jsonl` (JSON Lines) dengan skema standar.

### 3.1 Example Dataset

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

*Catatan: Contoh di atas hanya ilustrasi struktur data. Isi kutipan, atribusi, dan referensi hukum harus diverifikasi sebelum digunakan sebagai dataset.*

### 3.2 Field Standardization

| Field | Description |
|---|---|
| `chunk_id` | ID unik setiap chunk. |
| `doc_id` | ID unik dokumen sumber. |
| `source_category` | Kategori sumber literatur. |
| `language` | Bahasa konten. |
| `hierarchy` | Struktur kitab, bab, dan pembahasan. |
| `arabic_raw` | Teks Arab asli. |
| `arabic_clean` | Teks Arab hasil normalisasi. |
| `indonesian` | Terjemahan atau penjelasan. |
| `embedding_text` | Teks yang digunakan untuk embedding. |
| `citation` | Referensi bibliografi dan URL. |
| `metadata` | Metadata tambahan dan status verifikasi. |

### 3.3 Source Category Enumeration

```typescript
type SourceCategory =
  | "bahtsul_masail"
  | "kitab_turats"
  | "hadith"
  | "quran_tafsir"
  | "fatwa"
  | "qawaid_fiqh";
```

### 3.4 Verification Status

Setiap dokumen perlu memiliki status verifikasi.

```typescript
type VerificationStatus =
  | "pending"
  | "machine_verified"
  | "scholarly_verified"
  | "rejected";
```

Status tersebut memiliki arti:

- `pending`: Belum melalui proses verifikasi.
- `machine_verified`: Telah lolos validasi teknis otomatis.
- `scholarly_verified`: Telah diperiksa oleh reviewer yang kompeten.
- `rejected`: Tidak memenuhi standar kualitas dataset.

Validasi mesin tidak boleh disamakan dengan validasi keilmuan.

### 3.5 Arabic Normalization Rules

**arabic_raw**

Harus mempertahankan teks asli tanpa modifikasi.

**arabic_clean**

Digunakan untuk indexing dengan aturan:

- Menghilangkan harakat.
- Menghilangkan tatweel.
- Unifikasi karakter Alif.
- Unifikasi karakter Ya.
- Mempertahankan hubungan dengan teks asli.

### 3.6 Embedding Text Construction

Field `embedding_text` wajib menyertakan hierarki pembahasan.

Contoh:

```text
Kategori: Kitab Turats

Hierarki:
Fathul Mu'in > Kitab Shalat > Bab Syarat Shalat

Konteks:
Pembahasan mengenai syarat sah pelaksanaan shalat.

Ibarat:
[Original Arabic Text]
```

### 3.7 Semantic Chunking Rules

- Tidak menggunakan pemotongan karakter secara buta.
- Mempertahankan satu kesatuan pembahasan.
- Menyertakan hierarki pada setiap chunk.
- Memisahkan catatan kaki ke `metadata.footnotes`.
- Mempertahankan relasi matan dan syarah.
- Mempertahankan relasi antar-chunk jika satu pembahasan terlalu panjang.

---

## 4. Fine-Tuning Strategy

Fine-tuning bukan digunakan untuk memasukkan hafalan kitab ke dalam memori model.

Fine-tuning berfungsi meningkatkan kemampuan model dalam memahami istilah, mengikuti instruksi, dan melakukan grounding.

### 4.1 Strict Grounding & Abstention Training

Melatih model menggunakan pasangan contoh positif dan negatif.

Fokus:

- Menolak pertanyaan tanpa referensi.
- Menghindari pengetahuan eksternal.
- Membedakan konteks relevan dan tidak relevan.
- Mengikuti aturan sitasi.
- Mengidentifikasi informasi yang tidak tersedia.

### 4.2 Domain Adaptation: Turats Terminology

Meningkatkan pemahaman model terhadap terminologi:

- Fiqih.
- Ushul Fiqih.
- Qawaid Fiqhiyyah.
- Mushthalah Hadits.
- Istilah klasik dalam Kitab Turats.

### 4.3 Consistent Answer Formatting

Membakukan format jawaban:

1. Ringkasan jawaban berdasarkan referensi.
2. Uraian pembahasan.
3. Kutipan *'ibarat*.
4. Referensi dan metadata.
5. Catatan keterbatasan jika terdapat perbedaan pendapat atau kekurangan sumber.

Format ini tidak boleh mendorong model menciptakan putusan hukum baru.

### 4.4 Embedding & Reranker Fine-Tuning

Melatih model menggunakan pasangan:

- Pertanyaan Bahasa Indonesia.
- Referensi Bahasa Arab.
- Label relevansi.
- Konteks pembahasan.

Tujuannya meningkatkan kualitas retrieval lintas bahasa.

---

## 5. Technology Stack

| Component | Technology |
|---|---|
| Data Processing | Python |
| Document Parsing | PyMuPDF, BeautifulSoup4 |
| Arabic Processing | PyArabic |
| Schema Validation | Pydantic, Zod |
| Data Format | JSONL |
| Database | PostgreSQL |
| Vector Search | pgvector / Qdrant |
| Sparse Search | pg_search / BM25 |
| Embedding | BAAI/bge-m3 |
| Reranker | BAAI/bge-reranker-v2-m3 |
| Backend | NestJS / Next.js |
| Worker Service | Python |
| LLM | OpenAI / Anthropic / Self-hosted Models |

### LLM Compatibility

Jamiyyah dirancang agar agnostik terhadap penyedia LLM.

Model yang dapat diintegrasikan antara lain:

- OpenAI GPT-4o.
- Anthropic Claude.
- Qwen.
- Model open-weight lainnya yang kompatibel.

Pemilihan model mempertimbangkan kualitas grounding, kemampuan multilingual, biaya inference, dan kebutuhan infrastruktur.

---

## 6. Monorepo Structure

```text
jamiyyah-project/
│
├── packages/
│   ├── schema/
│   │   └── # Pydantic & Zod schemas
│   │
│   ├── normalizer/
│   │   └── # Arabic normalization
│   │
│   ├── parsers/
│   │   └── # Shamela, Hadith, Bahtsul Masail parsers
│   │
│   └── rag-engine/
│       └── # Query Expansion, Hybrid Search,
│           # Reranker, Guardrails & Citation Validator
│
├── apps/
│   ├── api/
│   │   └── # REST / tRPC API
│   │
│   └── web/
│       └── # Q&A Interface & Reference Explorer
│
├── datasets/
│   ├── samples/
│   │   └── # Sample JSONL datasets
│   │
│   └── README.md
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_GUIDELINES.md
│   └── EVALUATION.md
│
├── README.md
├── LICENSE
└── .gitignore
```

---

## 7. Evaluation & Benchmarking

Keandalan Jamiyyah harus diukur menggunakan benchmark yang dapat direproduksi.

Beberapa metrik evaluasi yang direncanakan:

| Metric | Evaluation Purpose |
|---|---|
| Recall@K | Mengukur kemampuan menemukan referensi relevan. |
| MRR | Mengukur posisi dokumen relevan dalam hasil pencarian. |
| NDCG@K | Mengukur kualitas ranking hasil retrieval. |
| Citation Precision | Mengukur validitas referensi yang digunakan. |
| Citation Coverage | Mengukur proporsi klaim yang memiliki referensi. |
| Faithfulness | Mengukur kesesuaian jawaban dengan konteks. |
| Abstention Precision | Mengukur ketepatan sistem dalam menolak jawaban. |
| Abstention Recall | Mengukur kemampuan menolak pertanyaan yang tidak memiliki dukungan sumber. |

Benchmark harus mencakup:

- Pertanyaan dengan referensi yang tersedia.
- Pertanyaan tanpa referensi.
- Pertanyaan ambigu.
- Pertanyaan dengan beberapa pendapat.
- Pertanyaan dengan referensi yang saling bertentangan.
- Pertanyaan yang membutuhkan pengetahuan di luar cakupan database.

Hasil evaluasi digunakan untuk memperbaiki retrieval, prompting, reranking, dan validator.

---

## 8. Contribution Guidelines

Jamiyyah merupakan proyek open-source yang terbuka bagi:

- Software Engineer.
- AI / Machine Learning Engineer.
- NLP Researcher.
- Santri dan akademisi.
- Peneliti Fiqih dan Ushul Fiqih.
- Pegiat literasi Islam dan Turats.

### Engineering Contributions

- Pengembangan parser.
- Pengembangan Arabic Normalizer.
- Optimalisasi Hybrid Search.
- Pengembangan RAG Engine.
- Pengembangan Citation Validator.
- Pengembangan API dan Web Interface.

### AI & Research Contributions

- Eksperimen embedding multilingual.
- Fine-tuning reranker.
- Benchmark anti-halusinasi.
- Evaluasi entailment.
- Pengembangan abstention mechanism.

### Islamic Literature & Data Contributions

- Penambahan dataset Kitab Turats.
- Kurasi dan pentashihan teks.
- Validasi kutipan dan referensi.
- Penambahan dataset Bahtsul Masail.
- Penyusunan benchmark pertanyaan hukum Islam.

Setiap kontribusi dataset wajib mengikuti Canonical Schema dan Data Guidelines.

---

## 9. License & Copyright

Kode sumber Jamiyyah Project menggunakan **MIT License**.

Namun, lisensi perangkat lunak tidak secara otomatis memberikan hak untuk mendistribusikan seluruh literatur yang digunakan sebagai dataset.

Hak cipta dan ketentuan penggunaan atas:

- Kitab Turats.
- Terjemahan.
- Dataset Hadits.
- Kompilasi putusan Bahtsul Masail.
- Fatwa.
- Dokumen referensi lainnya.

Tetap mengikuti ketentuan masing-masing mualif, penerbit, lembaga, dan pemegang hak terkait.

Setiap kontributor bertanggung jawab memastikan sumber data yang ditambahkan memiliki dasar penggunaan dan distribusi yang sesuai.

---

## 10. Project Vision

Jamiyyah Project memiliki visi membangun ekosistem pengetahuan Islam berbasis teknologi AI yang transparan, terstruktur, dan dapat diverifikasi.

Kami percaya bahwa teknologi AI dapat membantu memperluas akses terhadap literatur Islam tanpa menghilangkan pentingnya otoritas keilmuan dan ketelitian dalam memahami sumber.

AI bukan pengganti ulama, bukan pengganti proses ijtihad, dan bukan otoritas dalam menetapkan hukum Islam.

AI dalam Jamiyyah berperan sebagai alat bantu untuk:

- Menemukan literatur.
- Menelusuri referensi.
- Memahami konteks pembahasan.
- Menerjemahkan teks.
- Membandingkan pendapat berdasarkan sumber.
- Menyajikan informasi dengan referensi yang dapat diverifikasi.

Ketika referensi tidak tersedia, sistem harus berani mengatakan tidak tahu.

**No Reference, No Answer.**

---

<p align="center">
  <strong>Jamiyyah Project</strong><br />
  Open Knowledge. Verifiable References. Responsible AI.
</p>