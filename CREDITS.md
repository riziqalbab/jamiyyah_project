# Credits & Dataset Sources

Dokumen ini mencatat seluruh **sumber dataset**, **atribusi literatur**, **status hak cipta/distribusi**, serta **kredit teknologi dan kontributor** dalam **Jamiyyah Project**.

Sesuai prinsip *Strict Grounding* dan *Verifiable Citation* (*Sanad Rujukan*), setiap sumber data yang masuk ke dalam pipeline Jamiyyah wajib memiliki kejelasan asal-usul (*provenance*) dan ketentuan penggunaan sebelum diproses maupun didistribusikan.

---

## 1. Sumber Dataset Aktif

Daftar berikut mencakup dataset yang saat ini berada di direktori `datasets/` (baik `unparsed/`, `parsed/`, maupun `samples/`).

| Dataset | Lokasi File | Kategori | Jumlah / Ukuran | Status Parsing & Verifikasi | Asal Sumber & Hak Cipta |
|---|---|---|---|---|---|
| **Dataset Hadits 9 Imam ("Sunnah")** | `datasets/unparsed/hadist/hadits.csv` → `datasets/parsed/hadist/hadits.jsonl` | `hadith` | 38.100 entri hadits (~71,54 MB CSV / ~188,78 MB JSONL) | Sudah diparsing ke JSONL (`verification_status: pending`) | **Sumber:** [Kaggle — `ronnieaban/sunnah`](https://www.kaggle.com/datasets/ronnieaban/sunnah) oleh **Ronnie Aban** (file asal: `Sunnah.csv`). **Lisensi Kaggle:** ODC Public Domain Dedication and Licence (PDDL) |
| **Kitab Fathul Qarib** | `datasets/unparsed/kitab_turats/fathul_qarib/fathul_qarib.pdf` → `datasets/parsed/kitab_turats/fathul_qarib.jsonl` | `kitab_turats` | 380 halaman PDF (~6,29 MB) + Shamela #35120 | Sudah diparsing ke JSONL (`verification_status: pending`) | **Mualif:** Syekh Muhammad bin Qasim Al-Ghazi. **Penerbit versi digital & terjemahan:** Pondok Pesantren Al-Khoirot Malang (`www.alkhoirot.com`). **Distribusi:** Private (perlu izin penerbit versi digital untuk redistribusi publik) |
| **Matan al-Ghayah wat-Taqrib** | `datasets/unparsed/kitab_turats/taqrib/taqrib.pdf` → `datasets/parsed/kitab_turats/taqrib.jsonl` | `kitab_turats` | 82 halaman PDF (~461 KB) / 138 chunk | Sudah diparsing ke JSONL (`verification_status: pending`) | **Mualif:** Qadhi Abu Syuja' Ahmad bin Al-Husain Al-Asfahani. **Penerjemah & Penerbit digital:** Suim Wahyudi, S.Pd.I / Konsultasi Agama Al-Khoirot di Facebook (`facebook.com/groups/konsultasiagamaislam`, 2014). **Distribusi:** Private (perlu izin penerjemah/penerbit versi digital untuk redistribusi publik) |
| **Canonical Schema Sample** | `datasets/samples/canonical_sample.jsonl` | `bahtsul_masail` (ilustrasi) | 1 record contoh | Contoh skema untuk pengujian (`tracked` di Git) | Disusun internal sebagai ilustrasi format *Jamiyyah Canonical Schema* (bukan rujukan hukum aktual) |

### Rincian Dataset Hadits 9 Imam (`hadits.jsonl`)

- **Sumber Asal (*Upstream*):** [`ronnieaban/sunnah`](https://www.kaggle.com/datasets/ronnieaban/sunnah) di Kaggle (diunggah oleh **Ronnie Aban**, file asal `Sunnah.csv`, 71,54 MB).
- **Lisensi Sumber:** **ODC Public Domain Dedication and Licence (PDDL)**.
- **Struktur Kolom Mentah:** `Perawi`, `Arab` (teks Arab berharakat), dan `Terjemahan` (terjemahan Bahasa Indonesia).
- **Status Kurasi Jamiyyah:** `verification_status: pending` (telah dikonversi ke Jamiyyah Canonical Schema melalui `packages/parsers/jamiyyah_parsers/hadith_csv.py`, namun belum melewati *scholarly verification* atas akurasi terjemahan maupun takhrij/derajat hadits).

Hasil parsing mencakup **38.100** entri hadits dari 9 kitab (*Kutubut Tis'ah*):

| Kitab / Koleksi | Jumlah Hadits |
|---|---:|
| Shahih Bukhari (`Bukhari`) | 6.638 |
| Sunan An-Nasai (`Nasai`) | 5.364 |
| Shahih Muslim (`Muslim`) | 4.928 |
| Sunan Abu Daud (`Abu Daud`) | 4.419 |
| Musnad Ahmad (`Ahmad`) | 4.305 |
| Sunan Ibnu Majah (`Ibnu Majah`) | 4.285 |
| Sunan At-Tirmidzi (`Tirmidzi`) | 3.625 |
| Sunan Ad-Darimi (`Darimi`) | 2.949 |
| Muwatta' Malik (`Malik`) | 1.587 |
| **Total** | **38.100** |

> **Catatan Distribusi:** Meskipun dataset asal berlisensi PDDL, file penuh (`datasets/unparsed/` dan `datasets/parsed/`) tetap **tidak** disimpan di GitHub karena ukuran file besar (lihat kebijakan penyimpanan di [`datasets/README.md`](datasets/README.md)), melainkan didistribusikan via storage eksternal / Hugging Face Hub. Untuk sumber yang izin redistribusi publiknya belum terkonfirmasi (seperti versi digital/terjemahan pihak ketiga), simpan pada repositori **Private**.

### Rincian Dataset Kitab Fathul Qarib (`fathul_qarib.pdf`)

- **Judul Lengkap:** *Terjemah Kitab Fathul Qorib (Fath Al-Qarib)* — *Fathul Qarib Al-Mujib fi Syarhi Alfazh Al-Taqrib* / *Al-Qawl Al-Mukhtar fi Syarh Ghayatil Ikhtishar* (Syarah atas *Matan Al-Ghayah wa At-Taqrib* karya Imam Abu Syuja').
- **Mualif Kitab Asal:** Syekh Muhammad bin Qasim bin Muhammad Al-Ghazi ibn Al-Gharabili Abu Abdillah Syamsuddin.
- **Penerbit Versi Digital & Terjemahan:** **Pondok Pesantren Al-Khoirot Malang** ([`alkhoirot.com`](http://www.alkhoirot.com/)).
- **Tautan Sumber Tercantum dalam PDF:**
  - `http://www.alkhoirot.org/2017/07/terjemah-kitab-fathul-qorib.html`
  - `http://www.alkhoirot.org/2012/05/terjemah-kitab-matan-taqrib.html`
- **Spesifikasi File:** PDF (380 halaman, ~6,29 MB, metadata pembuatan `2018-01-01`).
- **Status Hak Cipta & Distribusi:** Teks Arab matan/syarah klasik merupakan khazanah *turats*, namun naskah terjemahan Bahasa Indonesia dan kompilasi versi digital merupakan terbitan **Pondok Pesantren Al-Khoirot Malang**. File disimpan secara lokal/`unparsed` (atau repositori **Private**) dan tidak didistribusikan ulang secara publik tanpa izin tertulis penerbit versi digital.

### Rincian Dataset Matan al-Ghayah wat-Taqrib (`taqrib.jsonl`)

- **Judul Lengkap:** *Matan al-Ghayah wat-Taqrib* (*Matan Abi Syuja'* / *Ghayatul Ikhtishar*) — *Terjemahan Taqrib Lengkap*.
- **Mualif Kitab Asal:** Al-Qadhi Abu Syuja' Ahmad bin Al-Husain bin Ahmad Al-Asfahani.
- **Penerjemah & Penerbit Versi Digital:** **Suim Wahyudi, S.Pd.I**, 
- **Spesifikasi File:** PDF (82 halaman, ~461 KB, selesai diterjemahkan `2014-02-10`), diparsing menjadi **138** chunk dwibahasa (*Muqaddimah* + 16 *Kitab*) melalui `packages/parsers/jamiyyah_parsers/taqrib.py`.
- **Status Kurasi & Distribusi:** `verification_status: pending`. Teks Arab matan klasik merupakan khazanah *turats*, namun naskah terjemahan Bahasa Indonesia dan kompilasi versi digital mengikuti hak cipta penerjemah/penerbitnya (`Private-only` hingga ada izin redistribusi publik).

---

## 2. Sumber Data Terencana (*Planned Sources*)

Sumber literatur berikut direncanakan dalam arsitektur pipeline Jamiyyah (lihat [`readme.md`](readme.md) dan `packages/parsers/`) dan wajib dilengkapi entri atribusinya saat mulai di-ingest:

| Sumber / Lembaga | Kategori (`source_category`) | Format Target | Catatan Atribusi & Hak Cipta |
|---|---|---|---|
| **Maktabah Shamela** | `kitab_turats` | `.bok` / SQLite | Mencatat nama kitab, *mualif*, *muhaqqiq*, penerbit, juz/halaman, serta sumber kompilasi digital |
| **NU Online / LBM PWNU / FMPP / Ahkamul Fuqaha** | `bahtsul_masail` | HTML / JSON / PDF | Mencatat lembaga penyelenggara, forum, tahun keputusan, URL resmi, dan kitab rujukan (*maraji'*) |
| **Dokumen Fatwa & Tafsir** | `fatwa`, `quran_tafsir` | PDF / HTML / JSON | Mencatat lembaga fatwa/mufassir, penerbit, tahun terbit, dan ketentuan penggunaan |
| **Qawaid Fiqhiyyah & Ushul Fiqih** | `qawaid_fiqh`, `kitab_turats` | PDF / `.bok` / JSON | Mencatat kitab induk, pengarang, dan edisi rujukan |

---

## 3. Panduan Pencatatan Sumber Dataset Baru

Setiap kontributor yang menambahkan dataset baru ke `datasets/unparsed/` atau `datasets/parsed/` **wajib** memperbarui tabel pada Bagian 1 dokumen ini dengan informasi berikut:

```markdown
- **Nama Dataset:** <nama kitab / koleksi>
- **Lokasi File:** `datasets/unparsed/<...>` → `datasets/parsed/<...>`
- **Kategori (`source_category`):** `hadith` | `kitab_turats` | `bahtsul_masail` | `quran_tafsir` | `fatwa` | `qawaid_fiqh`
- **Mualif / Penyusun / Penerjemah:** <nama pengarang asli, pentahqiq, atau penerjemah>
- **Sumber Asal (Upstream):** <URL resmi, repositori, penerbit, atau lembaga>
- **Lisensi & Status Distribusi:** <misal: Public Domain, CC BY-SA, Izin Tertulis, atau Private-only>
- **Status Verifikasi:** `pending` | `machine_verified` | `scholarly_verified`
```

---

## 4. Kredit Teknologi, Model & Pustaka Open-Source

Jamiyyah Project dibangun di atas karya komunitas *open-source* dan riset berikut:

### Model AI & Retrieval
- **BAAI (`BAAI/bge-m3`)** — Model embedding multilingual untuk dense retrieval lintas bahasa (Indonesia–Arab).
- **BAAI (`BAAI/bge-reranker-v2-m3`)** — Cross-encoder reranker untuk penyaringan relevansi dokumen.

### Pemrosesan Data, Skema & Backend
- **Python** beserta ekosistem pustaka: **Pydantic**, **PyArabic**, **PyMuPDF**, dan **BeautifulSoup4**.
- **Hugging Face Hub (`huggingface_hub` / `datasets`)** — Distribusi dan pengelolaan versi dataset.
- **PostgreSQL**, **pgvector**, **Qdrant**, dan **pg_search / BM25** — Penyimpanan terstruktur, pencarian vektor, dan pencarian leksikal (*sparse retrieval*).
- **TypeScript**, **Zod**, **Next.js**, dan **NestJS** — Validasi skema lintas-bahasa serta antarmuka API & Web yang direncanakan.

---

## 5. Kontributor & Apresiasi

- **Penginisiasi & Maintainer:** `riziqalbab` ([`riziqliliulilalbab@gmail.com`](mailto:riziqliliulilalbab@gmail.com))
- **Penyedia Dataset & Penerbit Digital:**
  - **Ronnie Aban** — Penyedia dataset Hadits 9 Imam ([`ronnieaban/sunnah`](https://www.kaggle.com/datasets/ronnieaban/sunnah)) di Kaggle (ODC PDDL).
  - **Pondok Pesantren Al-Khoirot Malang** ([`alkhoirot.com`](http://www.alkhoirot.com/)) — Penerbit versi digital dan terjemahan Bahasa Indonesia *Kitab Fathul Qorib* (`fathul_qarib.pdf`).
- **Para Ulama, Mualif, Pentahqiq, dan Penerjemah:** Seluruh karya keilmuan dalam tradisi *turats*, ilmu hadits, tafsir, dan forum *Bahtsul Masail* yang menjadi fondasi literatur proyek ini.
- **Kontributor Terbuka:** Terbuka bagi *engineer*, peneliti NLP/IR, santri, dan akademisi yang berkontribusi dalam pengembangan parser, kurasi data, serta pentashihan rujukan.

---

## 6. Kebijakan Hak Cipta & Koreksi Atribusi

- Kode sumber Jamiyyah Project dilisensikan di bawah **MIT License** (lihat [`LICENSE`](LICENSE)).
- Lisensi MIT **hanya** berlaku untuk kode perangkat lunak dan dokumentasi proyek, **tidak** mengalihkan atau menggantikan hak cipta atas kitab, terjemahan, maupun kompilasi dataset pihak ketiga.
- Apabila Anda merupakan pemegang hak cipta, penerbit, atau penyusun dari salah satu sumber yang tercantum dan ingin memperbaiki atribusi atau mengajukan penyesuaian status distribusi, silakan hubungi pengelola repositori atau buka *issue* pada repositori proyek.
