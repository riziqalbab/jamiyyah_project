# Evaluation & Benchmarking

Pedoman evaluasi keandalan retrieval, sitasi, dan mekanisme abstention pada Jamiyyah Project.

## 1. Retrieval Metrics

- **Recall@K:** Proporsi referensi relevan yang berhasil ditemukan pada top-K hasil retrieval.
- **MRR (Mean Reciprocal Rank):** Mengukur posisi rata-rata dokumen relevan pertama.
- **NDCG@K:** Mengukur kualitas pengurutan relevansi dokumen.

## 2. Grounding & Abstention Metrics

- **Citation Precision:** Proporsi sitasi `[ID: <chunk_id>]` yang valid dan benar-benar mendukung klaim.
- **Citation Coverage:** Proporsi klaim informatif yang memiliki rujukan eksplisit.
- **Faithfulness:** Kesesuaian isi jawaban terhadap teks sumber tanpa tambahan pengetahuan eksternal.
- **Abstention Precision & Recall:** Ketepatan dan kelengkapan sistem dalam menerapkan *tawaqquf* saat referensi tidak mencukupi.

## 3. Skenario Uji Benchmark

- Pertanyaan dengan referensi langsung tersedia.
- Pertanyaan tanpa referensi di corpus (harus *tawaqquf*).
- Pertanyaan ambigu atau lintas pendapat/mazhab.
- Pertanyaan di luar cakupan database.
