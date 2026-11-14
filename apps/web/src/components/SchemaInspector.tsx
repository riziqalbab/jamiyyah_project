import { useEffect, useState, type FormEvent } from "react";
import type { HealthResponse, JamiyyahChunk } from "../types";

interface SchemaInspectorProps {
  health: HealthResponse | null;
  chunk: JamiyyahChunk | null;
  chunkError: string | null;
  onLoadChunk: (chunkId: string) => void;
}

export function SchemaInspector({
  health,
  chunk,
  chunkError,
  onLoadChunk,
}: SchemaInspectorProps) {
  const [chunkIdInput, setChunkIdInput] = useState(chunk?.chunk_id ?? "");

  useEffect(() => {
    if (chunk?.chunk_id) {
      setChunkIdInput(chunk.chunk_id);
    }
  }, [chunk?.chunk_id]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = chunkIdInput.trim();
    if (trimmed) {
      onLoadChunk(trimmed);
    }
  }

  return (
    <section className="tab-panel active" id="panel-inspector" role="tabpanel">
      <div className="inspector-grid">
        <div className="card">
          <div className="panel-header">
            <div>
              <h3>Statistik Korpus Aktif</h3>
              <p className="panel-subtitle">Distribusi kategori sumber &amp; status verifikasi</p>
            </div>
          </div>

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
