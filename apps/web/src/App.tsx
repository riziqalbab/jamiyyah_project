import { useCallback, useEffect, useRef, useState } from "react";
import { PanelLeft } from "lucide-react";
import { askQuestion, fetchBooks, fetchChunk, fetchHealth } from "./api";
import { ChatWorkspace } from "./components/ChatWorkspace";
import { MaktabahExplorer } from "./components/MaktabahExplorer";
import { SchemaInspector } from "./components/SchemaInspector";
import { Sidebar } from "./components/Sidebar";
import type {
  ActiveTab,
  BookSummary,
  ChatMessage,
  ChatThread,
  HealthResponse,
  JamiyyahChunk,
} from "./types";

const THREADS_STORAGE_KEY = "jamiyyah-chat-threads-v1";

function makeEmptyThread(): ChatThread {
  const now = Date.now();
  return {
    id: `thread-${now}-${Math.random().toString(36).slice(2, 7)}`,
    title: "Obrolan Baru",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

function loadSavedThreads(): ChatThread[] {
  try {
    const raw = localStorage.getItem(THREADS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatThread[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("jamiyyah-theme");
    return saved === "dark" ? "dark" : "light";
  });

  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 900);
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");
  const [threads, setThreads] = useState<ChatThread[]>(() => {
    const saved = loadSavedThreads();
    return saved.length > 0 ? saved : [makeEmptyThread()];
  });
  const [activeThreadId, setActiveThreadId] = useState<string>(() => {
    const saved = loadSavedThreads();
    return saved[0]?.id ?? "";
  });

  const [sending, setSending] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<JamiyyahChunk | null>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);

  const wasHadithLoading = useRef(false);

  // Ensure activeThreadId always resolves to an existing thread
  useEffect(() => {
    if (!threads.some((t) => t.id === activeThreadId)) {
      if (threads.length > 0) {
        setActiveThreadId(threads[0].id);
      } else {
        const fresh = makeEmptyThread();
        setThreads([fresh]);
        setActiveThreadId(fresh.id);
      }
    }
  }, [threads, activeThreadId]);

  useEffect(() => {
    try {
      const nonEmpty = threads.filter((t) => t.messages.length > 0).slice(0, 30);
      localStorage.setItem(THREADS_STORAGE_KEY, JSON.stringify(nonEmpty));
    } catch {
      // Ignore storage quota issues
    }
  }, [threads]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("jamiyyah-theme", theme);
  }, [theme]);

  const loadBooksList = useCallback(async () => {
    try {
      const list = await fetchBooks();
      setBooks(list);
    } catch {
      // Handled via health indicator
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const nextHealth = await fetchHealth();
      setHealth(nextHealth);
      setHealthError(null);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : "Error");
    }
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;

    async function poll() {
      try {
        const nextHealth = await fetchHealth();
        if (cancelled) return;
        setHealth(nextHealth);
        setHealthError(null);

        const finishedHadith = wasHadithLoading.current && !nextHealth.hadith_loading;
        wasHadithLoading.current = nextHealth.hadith_loading;

        if (finishedHadith) {
          void loadBooksList();
        }

        if (nextHealth.hadith_loading) {
          timer = window.setTimeout(poll, 1500);
        }
      } catch (err) {
        if (!cancelled) {
          setHealthError(err instanceof Error ? err.message : "Error");
        }
      }
    }

    void poll();
    void loadBooksList();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [loadBooksList]);

  const loadChunk = useCallback(async (chunkId: string) => {
    setChunkError(null);
    try {
      const data = await fetchChunk(chunkId);
      setSelectedChunk(data);
    } catch (err) {
      setChunkError(err instanceof Error ? err.message : "Gagal memuat chunk");
    }
  }, []);

  const handleOpenReader = useCallback(
    (chunkId: string) => {
      setActiveTab("maktabah");
      void loadChunk(chunkId);
    },
    [loadChunk]
  );

  const handleOpenInspector = useCallback(
    (chunkId: string) => {
      setActiveTab("inspector");
      void loadChunk(chunkId);
    },
    [loadChunk]
  );

  const handleNewChat = useCallback(() => {
    const existingEmpty = threads.find((t) => t.messages.length === 0);
    if (existingEmpty) {
      setActiveThreadId(existingEmpty.id);
      return;
    }
    const fresh = makeEmptyThread();
    setThreads((prev) => [fresh, ...prev]);
    setActiveThreadId(fresh.id);
  }, [threads]);

  const handleDeleteThread = useCallback(
    (threadId: string) => {
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== threadId);
        if (next.length === 0) {
          const fresh = makeEmptyThread();
          setActiveThreadId(fresh.id);
          return [fresh];
        }
        if (activeThreadId === threadId) {
          setActiveThreadId(next[0].id);
        }
        return next;
      });
    },
    [activeThreadId]
  );

  const handleSendMessage = useCallback(
    async (query: string, opts: { minScore: number; category: string }) => {
      const targetId = activeThreadId;
      const now = Date.now();
      const userMsg: ChatMessage = {
        id: `msg-${now}-u`,
        role: "user",
        content: query,
        createdAt: now,
        category: opts.category || undefined,
      };

      setThreads((prev) =>
        prev.map((t) => {
          if (t.id !== targetId) return t;
          const isFirst = t.messages.length === 0;
          const title = isFirst
            ? query.length > 42
              ? `${query.slice(0, 42)}...`
              : query
            : t.title;
          return {
            ...t,
            title,
            updatedAt: now,
            messages: [...t.messages, userMsg],
          };
        })
      );

      setSending(true);
      try {
        const res = await askQuestion({
          query,
          min_score: opts.minScore,
          category: opts.category || null,
        });
        const botMsg: ChatMessage = {
          id: `msg-${Date.now()}-a`,
          role: "assistant",
          content: res.answer ?? "",
          createdAt: Date.now(),
          askResult: res,
        };
        setThreads((prev) =>
          prev.map((t) =>
            t.id === targetId
              ? { ...t, updatedAt: Date.now(), messages: [...t.messages, botMsg] }
              : t
          )
        );
      } catch (err) {
        const errMsg: ChatMessage = {
          id: `msg-${Date.now()}-err`,
          role: "assistant",
          content: "",
          createdAt: Date.now(),
          error: err instanceof Error ? err.message : "Gagal menghubungi server API.",
        };
        setThreads((prev) =>
          prev.map((t) =>
            t.id === targetId
              ? { ...t, updatedAt: Date.now(), messages: [...t.messages, errMsg] }
              : t
          )
        );
      } finally {
        setSending(false);
      }
    },
    [activeThreadId]
  );

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? threads[0];
  const ragInfo = health?.rag;
  const headerSubtitle =
    activeTab === "chat"
      ? ragInfo?.llm_configured
        ? `${ragInfo.llm_model} · Strict Grounding`
        : "3-Layer RAG · Strict Grounding"
      : activeTab === "maktabah"
      ? "Maktabah & Reader Paralel"
      : "Inspektor pgvector & Canonical JSON";

  return (
    <div className="gpt-shell">
      <Sidebar
        open={sidebarOpen}
        onCloseMobile={() => {
          if (window.innerWidth < 900) setSidebarOpen(false);
        }}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        threads={threads.filter((t) => t.messages.length > 0)}
        activeThreadId={activeThreadId}
        onNewChat={handleNewChat}
        onSelectThread={setActiveThreadId}
        onDeleteThread={handleDeleteThread}
        health={health}
        healthError={healthError}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
      />

      <div className="main-stage">
        <header className="stage-header">
          <div className="stage-header-left">
            <button
              type="button"
              className="sidebar-icon-btn"
              onClick={() => setSidebarOpen((prev) => !prev)}
              aria-label="Toggle sidebar"
              title="Buka / Tutup Sidebar"
            >
              <PanelLeft size={18} />
            </button>
            <div className="stage-brand">
              <span className="stage-title">Jamiyyah</span>
              <span className="stage-badge">{headerSubtitle}</span>
            </div>
          </div>

          <div className="stage-header-right">
            {health?.rag && (
              <span className="rag-chip" title="Embedding & Vector Store aktif">
                {health.rag.embedding_model} · {health.rag.vector_backend}
              </span>
            )}
          </div>
        </header>

        <div className="stage-body">
          {activeTab === "chat" && (
            <ChatWorkspace
              messages={activeThread?.messages ?? []}
              loading={sending}
              onSendMessage={(q, opts) => void handleSendMessage(q, opts)}
              onOpenReader={handleOpenReader}
              onOpenInspector={handleOpenInspector}
            />
          )}

          {activeTab === "maktabah" && (
            <div className="subview-scroll">
              <MaktabahExplorer
                books={books}
                activeChunk={selectedChunk}
                onSelectChunk={loadChunk}
                onOpenInspector={handleOpenInspector}
              />
            </div>
          )}

          {activeTab === "inspector" && (
            <div className="subview-scroll">
              <SchemaInspector
                health={health}
                chunk={selectedChunk}
                chunkError={chunkError}
                onLoadChunk={loadChunk}
                onRefreshHealth={() => void refreshHealth()}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
