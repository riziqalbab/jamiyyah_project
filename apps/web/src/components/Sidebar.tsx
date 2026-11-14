import {
  BookOpen,
  Database,
  MessageSquare,
  Moon,
  PanelLeftClose,
  Plus,
  Sun,
  Trash2,
} from "lucide-react";
import type { ActiveTab, ChatThread, HealthResponse } from "../types";

interface SidebarProps {
  open: boolean;
  onCloseMobile: () => void;
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  threads: ChatThread[];
  activeThreadId: string;
  onNewChat: () => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  health: HealthResponse | null;
  healthError: string | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function Sidebar({
  open,
  onCloseMobile,
  activeTab,
  onSelectTab,
  threads,
  activeThreadId,
  onNewChat,
  onSelectThread,
  onDeleteThread,
  health,
  healthError,
  theme,
  onToggleTheme,
}: SidebarProps) {
  let corpusLabel = "Memuat korpus...";
  if (healthError) {
    corpusLabel = "API terputus";
  } else if (health) {
    const total = health.total_chunks.toLocaleString("id-ID");
    corpusLabel = health.hadith_loading
      ? `${total} rujukan (+hadits...)`
      : `${total} rujukan siap`;
  }

  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onCloseMobile} />}
      <aside className={`sidebar ${open ? "open" : "collapsed"}`} aria-label="Navigasi utama">
        <div className="sidebar-top">
          <button
            type="button"
            className="new-chat-btn"
            onClick={() => {
              onNewChat();
              onSelectTab("chat");
              onCloseMobile();
            }}
          >
            <Plus size={16} />
            <span>Obrolan Baru</span>
          </button>

          <button
            type="button"
            className="sidebar-icon-btn mobile-only"
            onClick={onCloseMobile}
            aria-label="Tutup sidebar"
          >
            <PanelLeftClose size={18} />
          </button>
        </div>

        <nav className="sidebar-nav-section" aria-label="Mode workspace">
          <button
            type="button"
            className={`sidebar-nav-item ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => {
              onSelectTab("chat");
              onCloseMobile();
            }}
          >
            <MessageSquare size={16} />
            <span>Chat Kitab</span>
          </button>
          <button
            type="button"
            className={`sidebar-nav-item ${activeTab === "maktabah" ? "active" : ""}`}
            onClick={() => {
              onSelectTab("maktabah");
              onCloseMobile();
            }}
          >
            <BookOpen size={16} />
            <span>Jelajah Kitab</span>
          </button>
          <button
            type="button"
            className={`sidebar-nav-item ${activeTab === "inspector" ? "active" : ""}`}
            onClick={() => {
              onSelectTab("inspector");
              onCloseMobile();
            }}
          >
            <Database size={16} />
            <span>Inspektor RAG &amp; Skema</span>
          </button>
        </nav>

        <div className="sidebar-history-header">Riwayat Obrolan</div>
        <div className="sidebar-history">
          {threads.length === 0 ? (
            <div className="sidebar-empty">Belum ada obrolan tersimpan.</div>
          ) : (
            threads.map((thread) => (
              <div
                key={thread.id}
                className={`history-item ${
                  activeTab === "chat" && thread.id === activeThreadId ? "active" : ""
                }`}
              >
                <button
                  type="button"
                  className="history-item-btn"
                  onClick={() => {
                    onSelectThread(thread.id);
                    onSelectTab("chat");
                    onCloseMobile();
                  }}
                  title={thread.title}
                >
                  <MessageSquare size={14} />
                  <span className="history-title">{thread.title}</span>
                </button>
                <button
                  type="button"
                  className="history-delete-btn"
                  aria-label={`Hapus ${thread.title}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteThread(thread.id);
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-corpus-status">
            <span
              className={`status-dot ${health && !health.hadith_loading ? "ready" : ""}`}
            />
            <span className="corpus-text">{corpusLabel}</span>
          </div>
          <button
            type="button"
            className="sidebar-icon-btn"
            onClick={onToggleTheme}
            aria-label="Ubah tema"
            title={theme === "dark" ? "Mode Terang" : "Mode Gelap"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </aside>
    </>
  );
}
