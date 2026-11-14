import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBooks, fetchChunk, fetchHealth } from "./api";
import { MaktabahExplorer } from "./components/MaktabahExplorer";
import { QaWorkspace } from "./components/QaWorkspace";
import { SchemaInspector } from "./components/SchemaInspector";
import { TopBar } from "./components/TopBar";
import type { ActiveTab, BookSummary, HealthResponse, JamiyyahChunk } from "./types";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("jamiyyah-theme");
    return saved === "dark" ? "dark" : "light";
  });
  const [activeTab, setActiveTab] = useState<ActiveTab>("qa");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [books, setBooks] = useState<BookSummary[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<JamiyyahChunk | null>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);

  const wasHadithLoading = useRef(false);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("jamiyyah-theme", theme);
  }, [theme]);

  const loadBooksList = useCallback(async () => {
    try {
      const list = await fetchBooks();
      setBooks(list);
    } catch {
      // Handled silently; health banner already surfaces API connectivity.
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

  return (
    <div className="app-shell">
      <TopBar
        health={health}
        healthError={healthError}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
      />

      <nav className="mode-tabs" role="tablist" aria-label="Mode utama">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "qa"}
          className={`tab-btn ${activeTab === "qa" ? "active" : ""}`}
          id="tab-btn-qa"
          onClick={() => setActiveTab("qa")}
        >
          <span className="tab-label">Tanya Kitab</span>
          <span className="tab-hint">Q&amp;A + Tawaqquf</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "maktabah"}
          className={`tab-btn ${activeTab === "maktabah" ? "active" : ""}`}
          id="tab-btn-maktabah"
          onClick={() => setActiveTab("maktabah")}
        >
          <span className="tab-label">Jelajah Kitab</span>
          <span className="tab-hint">Maktabah &amp; 'Ibarat</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "inspector"}
          className={`tab-btn ${activeTab === "inspector" ? "active" : ""}`}
          id="tab-btn-inspector"
          onClick={() => setActiveTab("inspector")}
        >
          <span className="tab-label">Inspektor Skema &amp; Guardrails</span>
          <span className="tab-hint">Canonical JSONL</span>
        </button>
      </nav>

      <main className="workspace">
        {activeTab === "qa" && (
          <QaWorkspace
            onOpenReader={handleOpenReader}
            onOpenInspector={handleOpenInspector}
          />
        )}
        {activeTab === "maktabah" && (
          <MaktabahExplorer
            books={books}
            activeChunk={selectedChunk}
            onSelectChunk={loadChunk}
            onOpenInspector={handleOpenInspector}
          />
        )}
        {activeTab === "inspector" && (
          <SchemaInspector
            health={health}
            chunk={selectedChunk}
            chunkError={chunkError}
            onLoadChunk={loadChunk}
          />
        )}
      </main>
    </div>
  );
}
