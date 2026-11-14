import { Moon, Sun } from "lucide-react";
import type { HealthResponse } from "../types";

interface TopBarProps {
  health: HealthResponse | null;
  healthError: string | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
}

export function TopBar({ health, healthError, theme, onToggleTheme }: TopBarProps) {
  let statusText = "Memuat korpus...";
  if (healthError) {
    statusText = `Gagal terhubung ke API (${healthError})`;
  } else if (health) {
    const total = health.total_chunks.toLocaleString("id-ID");
    const suffix = health.hadith_loading ? " (mengindeks hadits...)" : "";
    statusText = `${total} rujukan terindeks${suffix}`;
  }

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-seal" aria-hidden="true">
          ج
        </div>
        <div className="brand-copy">
          <div className="brand-title-row">
            <h1>Jamiyyah</h1>
            <span className="badge badge-accent">Strict Grounding · 3-Layer RAG</span>
          </div>
          <p className="brand-subtitle">
            Mesin Pencari Turats &amp; Rujukan Syariat Berbasis Kutipan Primer
          </p>
        </div>
      </div>

      <div className="topbar-controls">
        <div className="corpus-pill" title="Status indeks korpus lokal">
          <span
            className={`status-dot ${health && !health.hadith_loading ? "ready" : ""}`}
          />
          <span>{statusText}</span>
        </div>

        <button
          type="button"
          className="btn-icon"
          onClick={onToggleTheme}
          aria-label="Ubah tema tampilan"
          title="Ubah tema Terang / Gelap"
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </div>
    </header>
  );
}
