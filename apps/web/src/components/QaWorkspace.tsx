import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { BookOpen, Code2, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { askQuestion } from "../api";
import type { AskResponse } from "../types";

interface QaWorkspaceProps {
  onOpenReader: (chunkId: string) => void;
  onOpenInspector: (chunkId: string) => void;
}

interface QuickPrompt {
  label: string;
  query: string;
  isTawaqquf?: boolean;
}

const QUICK_PROMPTS: QuickPrompt[] = [
  {
    label: "Macam Air & Dua Qullah",
    query: "Apa saja macam air yang sah untuk bersuci dan ukuran dua qullah?",
  },
  {
    label: "Rukun Shalat (Taqrib)",
    query: "Apa saja rukun shalat menurut Matan Taqrib?",
  },
  {
    label: "Syarat Akad Salam",
    query: "Bagaimana syarat akad salam dan batasannya?",
  },
  {
    label: "Paylater & Riba (Bahtsul Masail)",
    query: "Hukum transaksi paylater dan riba",
  },
  {
    label: "Uji Tawaqquf (Di Luar Korpus)",
    query: "Bagaimana prediksi harga saham teknologi dan kripto besok?",
    isTawaqquf: true,
  },
];

function renderInlineNodes(
  text: string,
  activeCid: string | null,
  onSelectCitation: (cid: string) => void
): ReactNode[] {
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*]+\*|\[ID:\s*[^\]]+\])/g;
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const key = `${match.index}-${token}`;

    if (token.startsWith("**") && token.endsWith("**")) {
      parts.push(
        <strong key={key}>
          {renderInlineNodes(token.slice(2, -2), activeCid, onSelectCitation)}
        </strong>
      );
    } else if (token.startsWith("*") && token.endsWith("*")) {
      parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith("[ID:")) {
      const cid = token.slice(4, -1).trim();
      parts.push(
        <button
          key={key}
          type="button"
          className={`cite-pill ${activeCid === cid ? "active" : ""}`}
          onClick={() => onSelectCitation(cid)}
          title={`Sorot sumber ${cid}`}
        >
          [ID: {cid}]
        </button>
      );
    }
    lastIndex = tokenRegex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function AnswerMarkdown({
  markdown,
  activeCid,
  onSelectCitation,
}: {
  markdown: string;
  activeCid: string | null;
  onSelectCitation: (cid: string) => void;
}) {
  const lines = markdown.split("\n");
  const blocks: ReactNode[] = [];
  let listItems: string[] = [];

  const flushList = (idxKey: number) => {
    if (listItems.length === 0) return;
    blocks.push(
      <ul className="answer-bullets" key={`list-${idxKey}`}>
        {listItems.map((item, idx) => (
          <li key={idx}>{renderInlineNodes(item, activeCid, onSelectCitation)}</li>
        ))}
      </ul>
    );
    listItems = [];
  };

  lines.forEach((rawLine, idx) => {
    const line = rawLine.trim();
    if (!line) {
      flushList(idx);
      return;
    }
    if (line.startsWith("- ")) {
      listItems.push(line.slice(2));
      return;
    }
    flushList(idx);
    if (line.startsWith("> ")) {
      blocks.push(
        <blockquote className="answer-note" key={`quote-${idx}`}>
          {renderInlineNodes(line.slice(2), activeCid, onSelectCitation)}
        </blockquote>
      );
    } else {
      blocks.push(
        <p key={`p-${idx}`}>{renderInlineNodes(line, activeCid, onSelectCitation)}</p>
      );
    }
  });
  flushList(lines.length);

  return <>{blocks}</>;
}

export function QaWorkspace({ onOpenReader, onOpenInspector }: QaWorkspaceProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [threshold, setThreshold] = useState(0.65);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [activeCid, setActiveCid] = useState<string | null>(null);

  const sourceCardRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!activeCid) return;
    const node = sourceCardRefs.current[activeCid];
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeCid]);

  async function runQuery(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const data = await askQuestion({
        query: trimmed,
        min_score: threshold,
        category: category || null,
      });
      setResult(data);
      setActiveCid(data.sources?.[0]?.chunk.chunk_id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void runQuery(query);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void runQuery(query);
    }
  }

  const expansionSummary = result
    ? result.expansion.concepts.map((c) => `${c.id} → ${c.ar.join(", ")}`).join(" | ") ||
      result.expansion.id_terms.join(", ") ||
      "—"
    : "—";

  return (
    <section className="tab-panel active" id="panel-qa" role="tabpanel">
      <div className="card qa-composer">
        <form onSubmit={handleSubmit} className="qa-form">
          <label htmlFor="qa-input" className="field-label">
            Ajukan pertanyaan fikih atau rujukan kitab (Bahasa Indonesia / istilah Arab)
          </label>
          <div className="qa-input-row">
            <textarea
              id="qa-input"
              rows={2}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Contoh: Apa saja macam air yang sah untuk bersuci dan ukuran dua qullah?"
              required
            />
            <button type="submit" className="btn-primary" id="qa-submit" disabled={loading}>
              <Search size={16} />
              <span>{loading ? "Menelusuri..." : "Telusuri Rujukan"}</span>
            </button>
          </div>

          <div className="qa-options-row">
            <div className="qa-filter-group">
              <label htmlFor="qa-category-filter" className="mini-label">
                Sumber:
              </label>
              <select
                id="qa-category-filter"
                className="select-compact"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">Semua Korpus</option>
                <option value="kitab_turats">Kitab Turats</option>
                <option value="hadith">Hadits</option>
                <option value="bahtsul_masail">Bahtsul Masail</option>
                <option value="quran">Al-Qur'an</option>
              </select>
            </div>

            <div className="qa-threshold-group">
              <label htmlFor="threshold-slider" className="mini-label">
                Ambang Layer 1 Gate: <strong>{threshold.toFixed(2)}</strong>
              </label>
              <input
                type="range"
                id="threshold-slider"
                min="0.35"
                max="0.90"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
              />
            </div>
          </div>
        </form>

        <div className="chips-bar">
          <span className="chips-label">Coba cepat:</span>
          {QUICK_PROMPTS.map((chip) => (
            <button
              key={chip.label}
              type="button"
              className={`chip ${chip.isTawaqquf ? "chip-tawaqquf" : ""}`}
              onClick={() => {
                setQuery(chip.query);
                void runQuery(chip.query);
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      {result && (
        <div className="telemetry-strip" id="telemetry-strip">
          <div className="telemetry-card">
            <span className="telemetry-step">Ekspansi Kueri (ID → AR)</span>
            <div className="telemetry-value">{expansionSummary}</div>
          </div>
          <div className="telemetry-card">
            <span className="telemetry-step">Layer 1 · Retrieval Gate</span>
            <div className="telemetry-value">
              {result.layer1_gate.passed
                ? `LOLOS (${result.layer1_gate.top_score.toFixed(3)} ≥ ${result.threshold.toFixed(2)})`
                : `TAWAQQUF (${result.layer1_gate.top_score.toFixed(3)} < ${result.threshold.toFixed(2)})`}
            </div>
          </div>
          <div className="telemetry-card">
            <span className="telemetry-step">Layer 2 · Grounding Config</span>
            <div className="telemetry-value">
              temp {result.grounding_config.temperature.toFixed(1)} · strict citation
            </div>
          </div>
          <div className="telemetry-card">
            <span className="telemetry-step">Layer 3 · Validasi Kutipan</span>
            <div className="telemetry-value">
              {result.status === "answered"
                ? `VALID (${result.layer3_validation.cited_ids.length} kutipan terikat)`
                : "DITAHAN (tidak ada generasi)"}
            </div>
          </div>
        </div>
      )}

      <div className="qa-grid">
        <div className="qa-answer-col">
          {!result && !error && (
            <div className="card empty-state">
              <div className="empty-ornament" aria-hidden="true">
                ﷽
              </div>
              <h2>Menjaga Amanah Ilmu dengan Kutipan Terverifikasi</h2>
              <p>
                Setiap jawaban hanya disusun dari teks primer dalam korpus lokal. Jika bukti rujukan
                berada di bawah ambang <code>min_reranker_score</code>, mesin otomatis memilih sikap{" "}
                <strong>Tawaqquf</strong> alih-alih berspekulasi.
              </p>
            </div>
          )}

          {error && (
            <div className="card answer-card">
              <div className="tawaqquf-box">
                <h3>Kesalahan Permintaan</h3>
                <p>{error}</p>
              </div>
            </div>
          )}

          {result && (
            <article className="card answer-card" id="qa-result">
              <header className="answer-header">
                <span
                  className={`status-pill ${
                    result.status === "answered" ? "answered" : "tawaqquf"
                  }`}
                >
                  {result.status === "answered" ? (
                    <>
                      <ShieldCheck size={15} /> Terjawab · Terikat Kutipan Primer
                    </>
                  ) : (
                    <>
                      <ShieldAlert size={15} /> Tawaqquf · Bukti Tidak Memenuhi Ambang
                    </>
                  )}
                </span>
                <span className="answer-meta">
                  Skor puncak: {result.layer1_gate.top_score.toFixed(3)} | Ambang:{" "}
                  {result.threshold.toFixed(2)}
                </span>
              </header>

              <div className="answer-body">
                {result.status === "answered" && result.answer ? (
                  <AnswerMarkdown
                    markdown={result.answer}
                    activeCid={activeCid}
                    onSelectCitation={setActiveCid}
                  />
                ) : (
                  <div className="tawaqquf-box">
                    <h3>Tawaqquf — Menahan Jawaban</h3>
                    <p>
                      Maaf, tidak ditemukan rujukan primer dalam korpus yang memenuhi ambang
                      keyakinan (<code>min_reranker_score = {result.threshold.toFixed(2)}</code>).
                      Sesuai prinsip kehati-hatian ilmiah, sistem memilih{" "}
                      <strong>tidak berspekulasi</strong>.
                    </p>
                    <p>
                      <strong>Alasan Layer 1 Gate:</strong>{" "}
                      <code>{result.layer1_gate.reason}</code>
                    </p>
                  </div>
                )}
              </div>

              <footer className="answer-footer">
                {result.status === "answered" ? (
                  <>
                    <span>
                      Layer 3 Validasi: {result.layer3_validation.cited_ids.length} ID terverifikasi
                    </span>
                    <span>External knowledge: disabled</span>
                  </>
                ) : (
                  <span>
                    Coba perjelas istilah fikih atau sesuaikan slider ambang untuk inspeksi.
                  </span>
                )}
              </footer>
            </article>
          )}
        </div>

        <aside className="qa-sources-col">
          <div className="card sources-panel">
            <div className="panel-header">
              <div>
                <h3>Sanad Rujukan &amp; 'Ibarat Asli</h3>
                <p className="panel-subtitle">
                  {result?.status === "tawaqquf"
                    ? "Kandidat terdekat ditampilkan untuk transparansi audit (belum lolos Layer 1 Gate)."
                    : "Klik tag [ID: ...] pada jawaban untuk menyorot 'ibarat Arab dan sanad aslinya."}
                </p>
              </div>
            </div>

            <div className="sources-list">
              {!result || result.sources.length === 0 ? (
                <div className="sources-placeholder">
                  {result
                    ? "Tidak ada kandidat terdekat yang cocok di korpus lokal."
                    : "Belum ada rujukan dimuat. Ajukan pertanyaan atau pilih salah satu contoh di atas."}
                </div>
              ) : (
                result.sources.map((item) => {
                  const chunk = item.chunk;
                  const cid = chunk.chunk_id;
                  const ref =
                    chunk.citation.full_reference || chunk.citation.short_label || cid;
                  const verif = chunk.metadata.verification_status || "pending";
                  const arRaw = chunk.content.arabic_raw || "";
                  const indo = chunk.content.indonesian || "";

                  return (
                    <article
                      key={cid}
                      ref={(el) => {
                        sourceCardRefs.current[cid] = el;
                      }}
                      className={`source-card ${activeCid === cid ? "highlighted" : ""}`}
                      onClick={() => setActiveCid(cid)}
                    >
                      <div className="source-card-top">
                        <span className="source-id">{cid}</span>
                        <span className="source-score">
                          rerank {item.rerank_score.toFixed(3)} · RRF {item.rrf_score.toFixed(4)}
                        </span>
                      </div>
                      <div className="source-ref">{ref}</div>
                      <div className="source-badges">
                        <span className="badge badge-accent">{chunk.source_category}</span>
                        <span className={`verif-badge verif-${verif}`}>{verif}</span>
                        {chunk.metadata.madzhab && (
                          <span className="badge">madzhab: {chunk.metadata.madzhab}</span>
                        )}
                      </div>
                      {arRaw && (
                        <div className="source-ar" dir="rtl" lang="ar">
                          {arRaw.length > 340 ? `${arRaw.slice(0, 340)}...` : arRaw}
                        </div>
                      )}
                      {indo && (
                        <div className="source-id-text">
                          {indo.length > 260 ? `${indo.slice(0, 260)}...` : indo}
                        </div>
                      )}
                      <div className="source-actions">
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenReader(cid);
                          }}
                        >
                          <BookOpen size={14} /> Baca Penuh
                        </button>
                        <button
                          type="button"
                          className="btn-ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenInspector(cid);
                          }}
                        >
                          <Code2 size={14} /> JSON
                        </button>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
