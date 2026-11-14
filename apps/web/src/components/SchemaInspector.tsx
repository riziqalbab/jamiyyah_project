import { useEffect, useState, type FormEvent } from "react";
import { fetchRagIndexStatus, triggerRagIndex } from "../api";
import type { HealthResponse, JamiyyahChunk, RagIndexJobStatus } from "../types";

interface SchemaInspectorProps {
  health: HealthResponse | null;
  chunk: JamiyyahChunk | null;
  chunkError: string | null;
  onLoadChunk: (chunkId: string) => void;
  onRefreshHealth?: () => void;
}

export function SchemaInspector({
  health,
  chunk,
  chunkError,
  onLoadChunk,
  onRefreshHealth,
}: SchemaInspectorProps) {
  const [chunkIdInput, setChunkIdInput] = useState(chunk?.chunk_id ?? "");
  const [includeHadith, setIncludeHadith] = useState(false);
  const [job, setJob] = useState<RagIndexJobStatus | null>(health?.rag?.index_job ?? null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  useEffect(() => {
    if (chunk?.chunk_id) {
      setChunkIdInput(chunk.chunk_id);
    }
  }, [chunk?.chunk_id]);

  useEffect(() => {
    if (health?.rag?.index_job && !job) {
      setJob(health.rag.index_job);
    }
  }, [health?.rag?.index_job, job]);

  useEffect(() => {
    if (!job?.running) return;
    let active = true;
    const timer = window.setInterval(async () => {
      try {
        const next = await fetchRagIndexStatus();
        if (!active) return;
        setJob(next);
        if (!next.running) {
          onRefreshHealth?.();
        }
      } catch (err) {
        if (active) {
          setTriggerError(err instanceof Error ? err.message : "Gagal memeriksa progres");
        }
      }
    }, 500);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [job?.running, onRefreshHealth]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = chunkIdInput.trim();
    if (trimmed) {
      onLoadChunk(trimmed);
    }
  }

  async function handleIndexClick() {
    setTriggerError(null);
    try {
      const started = await triggerRagIndex(includeHadith);
      setJob(started);
    } catch (err) {
      setTriggerError(
        err instanceof Error ? err.message : "Gagal memulai proses indexing"
      );
    }
  }

  const rag = health?.rag;
  const pg = rag?.pgvector;
  const showProgress = job && job.state !== "idle";
  const pct = job ? Math.max(0, Math.min(100, job.percent)) : 0;

  return (
    <section className="tab-panel active" id="panel-inspector" role="tabpanel">
      <div className="inspector-grid">
        <div className="card">
          <div className="panel-header">
            <div>
              <h3>Statistik Korpus &amp; Status RAG</h3>
              <p className="panel-subtitle">
                Konfigurasi pgvector, Ollama Embeddings, &amp; Cloud OpenAI-Compatible LLM
              </p>
            </div>
          </div>

          {rag && (
            <div className="rag-status-box">
              <div>
                <strong>Vector Store:</strong> <code>{rag.vector_backend}</code>
                {pg && (
                  <span>
                    {" · "}
                    {pg.connected
                      ? pg.schema_ready
                        ? `terhubung (${pg.count.toLocaleString("id-ID")} vektor)`
                        : "terhubung (tabel belum dibuat)"
                      : `offline (${pg.error ?? "cek PostgreSQL"})`}
                  </span>
                )}
              </div>
              <div>
                <strong>Embedding:</strong> <code>{rag.embedding_model}</code> @{" "}
                <code>{rag.embedding_base_url}</code> (
                {rag.indexed_vectors.toLocaleString("id-ID")} terindeks)
              </div>
              <div>
                <strong>Cloud LLM:</strong> <code>{rag.llm_model}</code> @{" "}
                <code>{rag.llm_base_url}</code> —{" "}
                <strong>
                  {rag.llm_configured ? "LLM_API_KEY aktif" : "LLM_API_KEY belum diset (fallback)"}
                </strong>
              </div>

              <div className="rag-index-actions">
                <label className="toggle-chip">
                  <input
                    type="checkbox"
                    checked={includeHadith}
                    disabled={Boolean(job?.running)}
                    onChange={(e) => setIncludeHadith(e.target.checked)}
                  />
                  <span>
                    Sertakan <code>hadits.jsonl</code> (38.100 entri)
                  </span>
                </label>

                <button
                  type="button"
                  className="btn-secondary"
                  disabled={Boolean(job?.running)}
                  onClick={() => void handleIndexClick()}
                >
                  {job?.running
                    ? `Mengindeks (${pct.toFixed(1)}%)...`
                    : includeHadith
                    ? "Indeks Semua (Kitab + Hadits) ke pgvector"
                    : "Indeks Kitab Turats ke pgvector (Ollama)"}
                </button>

                {showProgress && job && (
                  <div className="index-progress-card" role="status" aria-live="polite">
                    <div className="index-progress-head">
                      <span>
                        {job.state === "running"
                          ? `Memproses ${job.current_file || "..."}`
                          : job.state === "done"
                          ? "Indexing selesai"
                          : "Indexing gagal"}
                      </span>
                      <strong>{pct.toFixed(1)}%</strong>
                    </div>
                    <div
                      className="progress-track"
                      role="progressbar"
                      aria-valuenow={Math.round(pct)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <div
                        className={`progress-fill ${job.state}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="index-progress-stats">
                      <span>
                        Dipindai: {job.scanned.toLocaleString("id-ID")} /{" "}
                        {job.total.toLocaleString("id-ID")}
                      </span>
                      <span>Baru: {job.embedded.toLocaleString("id-ID")}</span>
                      <span>Dilewati: {job.skipped_unchanged.toLocaleString("id-ID")}</span>
                      {job.state === "done" && (
                        <span>Total di pgvector: {job.total_in_store.toLocaleString("id-ID")}</span>
                      )}
                    </div>
                    {job.error && <div className="rag-index-err">{job.error}</div>}
                  </div>
                )}

                {triggerError && <div className="rag-index-err">{triggerError}</div>}
              </div>
            </div>
          )}

          <div className="stats-grid">
            <div className="stat-tile">
              <div className="stat-label">Total Canonical Chunks</div>
              <div className="stat-number">
                {(health?.total_chunks ?? 0).toLocaleString("id-ID")}
              </div>
            </div>
            <div className="stat-tile">
              <div className="stat-label">Koleksi Kitab</div>
              <div className="stat-number">
                {Object.keys(health?.by_book ?? {}).length.toLocaleString("id-ID")}
              </div>
            </div>

            {Object.entries(health?.by_category ?? {}).map(([cat, count]) => (
              <div className="stat-tile" key={`cat-${cat}`}>
                <div className="stat-label">{cat}</div>
                <div className="stat-number">{count.toLocaleString("id-ID")}</div>
              </div>
            ))}

            {Object.entries(health?.by_verification_status ?? {}).map(([st, count]) => (
              <div className="stat-tile" key={`st-${st}`}>
                <div className="stat-label">Status: {st}</div>
                <div className="stat-number">{count.toLocaleString("id-ID")}</div>
              </div>
            ))}
          </div>

          <div className="loaded-files-box">
            <strong>Berkas JSONL aktif:</strong>
            <ul>
              {(health?.loaded_files ?? []).map((f) => (
                <li key={f}>
                  <code>{f}</code>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">
            <div>
              <h3>
                Inspektor Canonical Chunk (<code>JamiyyahChunk</code>)
              </h3>
              <p className="panel-subtitle">
                Masukkan <code>chunk_id</code> atau klik &quot;Lihat di Inspektor JSON&quot; dari
                tab lain
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="inspector-search-row">
            <input
              type="text"
              id="inspector-chunk-id"
              value={chunkIdInput}
              onChange={(e) => setChunkIdInput(e.target.value)}
              placeholder="Contoh: taqrib_thaharah_001"
            />
            <button type="submit" className="btn-secondary">
              Muat Chunk
            </button>
          </form>

          {chunk?.content.embedding_text && (
            <div className="embedding-preview">
              <h4>
                Teks Pengindeksan (<code>content.embedding_text</code>)
              </h4>
              <pre>{chunk.content.embedding_text}</pre>
            </div>
          )}

          <pre className="json-viewer">
            {chunkError
              ? `Gagal memuat chunk: ${chunkError}`
              : chunk
              ? JSON.stringify(chunk, null, 2)
              : "Pilih salah satu rujukan atau chunk untuk melihat struktur JSON kanoniknya."}
          </pre>
        </div>
      </div>
    </section>
  );
}
