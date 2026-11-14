import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import {
  ArrowUp,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Code2,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import type { ChatMessage, SearchHit } from "../types";

interface ChatWorkspaceProps {
  messages: ChatMessage[];
  loading: boolean;
  onSendMessage: (query: string, opts: { minScore: number; category: string }) => void;
  onOpenReader: (chunkId: string) => void;
  onOpenInspector: (chunkId: string) => void;
}

interface QuickPrompt {
  title: string;
  subtitle: string;
  query: string;
  isTawaqquf?: boolean;
}

const SUGGESTED_PROMPTS: QuickPrompt[] = [
  {
    title: "Macam Air & Dua Qullah",
    subtitle: "Fikih thaharah berdasarkan Matan Taqrib & syarahnya",
    query: "Apa saja macam air yang sah untuk bersuci dan ukuran dua qullah?",
  },
  {
    title: "Rukun Shalat (Taqrib)",
    subtitle: "Rincian rukun shalat dari kitab fikih Syafi'iyah",
    query: "Apa saja rukun shalat menurut Matan Taqrib?",
  },
  {
    title: "Syarat Akad Salam",
    subtitle: "Ketentuan muamalah jual beli pesanan dalam turats",
    query: "Bagaimana syarat akad salam dan batasannya?",
  },
  {
    title: "Uji Tawaqquf (Di Luar Korpus)",
    subtitle: "Buktikan abstention saat rujukan tidak memadai",
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
          title={`Lihat 'ibarat & sanad ${cid}`}
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

function AssistantMarkdown({
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
      <ul className="chat-bullets" key={`list-${idxKey}`}>
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
    if (line.startsWith("- ") || line.startsWith("* ")) {
      listItems.push(line.slice(2));
      return;
    }
    flushList(idx);
    if (line.startsWith("> ")) {
      blocks.push(
        <blockquote className="chat-quote" key={`quote-${idx}`}>
          {renderInlineNodes(line.slice(2), activeCid, onSelectCitation)}
        </blockquote>
      );
    } else if (line.startsWith("### ")) {
      blocks.push(
        <h4 className="chat-subheading" key={`h4-${idx}`}>
          {renderInlineNodes(line.slice(4), activeCid, onSelectCitation)}
        </h4>
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

export function ChatWorkspace({
  messages,
  loading,
  onSendMessage,
  onOpenReader,
  onOpenInspector,
}: ChatWorkspaceProps) {
  const [input, setInput] = useState("");
  const [category, setCategory] = useState("");
  const [threshold, setThreshold] = useState(0.65);
  const [showSettings, setShowSettings] = useState(false);

  const [drawerSources, setDrawerSources] = useState<SearchHit[] | null>(null);
  const [activeCid, setActiveCid] = useState<string | null>(null);
  const [expandedTelemetry, setExpandedTelemetry] = useState<Record<string, boolean>>({});

  const threadEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const sourceCardRefs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  useEffect(() => {
    if (!activeCid) return;
    sourceCardRefs.current[activeCid]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeCid, drawerSources]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [input]);

  function submitCurrent() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    setInput("");
    onSendMessage(trimmed, { minScore: threshold, category });
  }

  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    submitCurrent();
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitCurrent();
    }
  }

  function openCitationsForMessage(msg: ChatMessage, focusCid?: string) {
    const sources = msg.askResult?.sources ?? [];
    if (sources.length === 0) return;
    setDrawerSources(sources);
    setActiveCid(focusCid ?? sources[0].chunk.chunk_id);
  }

  return (
    <div className="chat-layout">
      <div className="chat-main">
        <div className="chat-scroll-area">
          {messages.length === 0 ? (
            <div className="chat-welcome">
              <div className="welcome-seal" aria-hidden="true">
                ج
              </div>
              <h2>Apa yang ingin Anda telusuri dalam turats?</h2>
              <p className="welcome-subtitle">
                Ajukan pertanyaan fikih atau hadits. Jawaban disusun ketat dari teks primer dengan
                tag <code>[ID: ...]</code>, atau memilih <strong>Tawaqquf</strong> bila bukti tidak
                mencukupi.
              </p>

              <div className="welcome-grid">
                {SUGGESTED_PROMPTS.map((item) => (
                  <button
                    key={item.title}
                    type="button"
                    className={`prompt-card ${item.isTawaqquf ? "tawaqquf" : ""}`}
                    onClick={() =>
                      onSendMessage(item.query, { minScore: threshold, category })
                    }
                  >
                    <div className="prompt-card-title">
                      <Sparkles size={14} />
                      <span>{item.title}</span>
                    </div>
                    <div className="prompt-card-sub">{item.subtitle}</div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-thread">
              {messages.map((msg) => {
                if (msg.role === "user") {
                  return (
                    <div key={msg.id} className="msg-row msg-user">
                      <div className="user-bubble">{msg.content}</div>
                    </div>
                  );
                }

                const res = msg.askResult;
                const isTelemetryOpen = Boolean(expandedTelemetry[msg.id]);
                const sources = res?.sources ?? [];
                const expansionText = res
                  ? res.expansion.concepts.map((c) => `${c.id} → ${c.ar.join(", ")}`).join(" | ") ||
                    res.expansion.id_terms.join(", ") ||
                    "—"
                  : "—";

                return (
                  <div key={msg.id} className="msg-row msg-assistant">
                    <div className="assistant-avatar" aria-hidden="true">
                      ج
                    </div>
                    <div className="assistant-content">
                      {msg.error && (
                        <div className="tawaqquf-box">
                          <h4>Terjadi Kesalahan</h4>
                          <p>{msg.error}</p>
                        </div>
                      )}

                      {res && (
                        <>
                          <div className="assistant-meta-bar">
                            <span
                              className={`status-pill ${
                                res.status === "answered" ? "answered" : "tawaqquf"
                              }`}
                            >
                              {res.status === "answered" ? (
                                <>
                                  <ShieldCheck size={13} /> Terverifikasi ·{" "}
                                  {res.rag_mode === "llm_grounded"
                                    ? res.llm_model || "Cloud LLM"
                                    : "Mode Ekstraktif"}
                                </>
                              ) : (
                                <>
                                  <ShieldAlert size={13} /> Tawaqquf · Skor{" "}
                                  {res.layer1_gate.top_score.toFixed(2)} &lt;{" "}
                                  {res.threshold.toFixed(2)}
                                </>
                              )}
                            </span>

                            <button
                              type="button"
                              className="telemetry-toggle-btn"
                              onClick={() =>
                                setExpandedTelemetry((prev) => ({
                                  ...prev,
                                  [msg.id]: !prev[msg.id],
                                }))
                              }
                            >
                              <span>Detail 3-Layer RAG</span>
                              {isTelemetryOpen ? (
                                <ChevronUp size={13} />
                              ) : (
                                <ChevronDown size={13} />
                              )}
                            </button>
                          </div>

                          {isTelemetryOpen && (
                            <div className="telemetry-inline-panel">
                              <div>
                                <strong>Ekspansi ID → AR:</strong> {expansionText}
                              </div>
                              <div>
                                <strong>Layer 1 Gate:</strong>{" "}
                                {res.layer1_gate.passed ? "LOLOS" : "TAWAQQUF"} (skor{" "}
                                {res.layer1_gate.top_score.toFixed(3)} vs{" "}
                                {res.threshold.toFixed(2)} · {res.retrieval_mode ?? "bm25"})
                              </div>
                              <div>
                                <strong>Layer 2 &amp; 3:</strong> temp{" "}
                                {res.grounding_config.temperature.toFixed(1)} ·{" "}
                                {res.layer3_validation.cited_ids.length} kutipan tervalidasi
                              </div>
                            </div>
                          )}

                          {res.status === "answered" && res.answer ? (
                            <div className="assistant-prose">
                              <AssistantMarkdown
                                markdown={res.answer}
                                activeCid={activeCid}
                                onSelectCitation={(cid) => openCitationsForMessage(msg, cid)}
                              />
                            </div>
                          ) : (
                            <div className="tawaqquf-box">
                              <h4>Tawaqquf — Menahan Jawaban</h4>
                              <p>
                                Tidak ditemukan rujukan primer yang melampaui ambang keyakinan{" "}
                                <code>{res.threshold.toFixed(2)}</code>. Sesuai kehati-hatian
                                ilmiah, sistem memilih <strong>tidak berspekulasi</strong>.
                              </p>
                              <p className="tawaqquf-reason">
                                <code>{res.layer1_gate.reason}</code>
                              </p>
                            </div>
                          )}

                          {sources.length > 0 && (
                            <div className="msg-sources-strip">
                              <button
                                type="button"
                                className="sources-trigger-btn"
                                onClick={() => openCitationsForMessage(msg)}
                              >
                                <BookOpen size={14} />
                                <span>
                                  {res.status === "tawaqquf"
                                    ? `Audit ${sources.length} Kandidat Terdekat`
                                    : `Lihat ${sources.length} Sanad Rujukan & 'Ibarat Arab`}
                                </span>
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}

              {loading && (
                <div className="msg-row msg-assistant">
                  <div className="assistant-avatar" aria-hidden="true">
                    ج
                  </div>
                  <div className="assistant-content">
                    <div className="typing-indicator">
                      <span className="typing-dots">
                        <i />
                        <i />
                        <i />
                      </span>
                      <span>Menelusuri kitab &amp; memvalidasi sitasi...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={threadEndRef} />
            </div>
          )}
        </div>

        <div className="composer-dock">
          {showSettings && (
            <div className="composer-settings-popover">
              <div className="setting-row">
                <label htmlFor="chat-category">Filter Sumber:</label>
                <select
                  id="chat-category"
                  className="select-compact"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  <option value="">Semua Korpus</option>
                  <option value="kitab_turats">Kitab Turats</option>
                  <option value="hadith">Hadits</option>
                  <option value="bahtsul_masail">Bahtsul Masail</option>
                  <option value="quran">Al-Qur&apos;an</option>
                </select>
              </div>
              <div className="setting-row">
                <label htmlFor="chat-threshold">
                  Ambang Layer 1 Gate: <strong>{threshold.toFixed(2)}</strong>
                </label>
                <input
                  id="chat-threshold"
                  type="range"
                  min="0.35"
                  max="0.90"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                />
              </div>
            </div>
          )}

          <form onSubmit={handleFormSubmit} className="composer-box">
            <textarea
              ref={textareaRef}
              id="qa-input"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Tanyakan masalah fikih, hadits, atau rujukan kitab..."
              disabled={loading}
            />

            <div className="composer-actions">
              <div className="composer-left-tools">
                <button
                  type="button"
                  className={`composer-tool-btn ${showSettings ? "active" : ""}`}
                  onClick={() => setShowSettings((prev) => !prev)}
                  title="Pengaturan filter sumber & ambang Tawaqquf"
                >
                  <SlidersHorizontal size={15} />
                  <span>
                    {category || "Semua"} · {threshold.toFixed(2)}
                  </span>
                </button>
              </div>

              <button
                type="submit"
                id="qa-submit"
                className="send-circle-btn"
                disabled={!input.trim() || loading}
                aria-label="Kirim pertanyaan"
                title="Kirim (Enter)"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </form>

          <div className="composer-footnote">
            Jamiyyah menjawab ketat dari korpus lokal dengan sitasi <code>[ID: ...]</code>, atau{" "}
            <em>Tawaqquf</em> bila rujukan tidak mencukupi.
          </div>
        </div>
      </div>

      {drawerSources && (
        <aside className="citations-drawer" aria-label="Sanad Rujukan & 'Ibarat Asli">
          <div className="citations-drawer-header">
            <div>
              <h3>Sanad Rujukan &amp; &apos;Ibarat</h3>
              <p>{drawerSources.length} sumber terambil</p>
            </div>
            <button
              type="button"
              className="sidebar-icon-btn"
              onClick={() => setDrawerSources(null)}
              aria-label="Tutup panel rujukan"
            >
              <X size={16} />
            </button>
          </div>

          <div className="citations-drawer-list">
            {drawerSources.map((item) => {
              const chunk = item.chunk;
              const cid = chunk.chunk_id;
              const ref = chunk.citation.full_reference || chunk.citation.short_label || cid;
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
                      rerank {item.rerank_score.toFixed(3)}
                      {item.dense_cosine ? ` · dense ${item.dense_cosine.toFixed(3)}` : ""}
                    </span>
                  </div>
                  <div className="source-ref">{ref}</div>
                  <div className="source-badges">
                    <span className="badge badge-accent">{chunk.source_category}</span>
                    <span className={`verif-badge verif-${verif}`}>{verif}</span>
                    {chunk.metadata.madzhab && (
                      <span className="badge">{chunk.metadata.madzhab}</span>
                    )}
                  </div>
                  {arRaw && (
                    <div className="source-ar" dir="rtl" lang="ar">
                      {arRaw.length > 360 ? `${arRaw.slice(0, 360)}...` : arRaw}
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
            })}
          </div>
        </aside>
      )}
    </div>
  );
}
