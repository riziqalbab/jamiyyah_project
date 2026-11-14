import { useEffect, useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { searchChunks } from "../api";
import type { BookSummary, JamiyyahChunk, SearchHit } from "../types";

interface MaktabahExplorerProps {
  books: BookSummary[];
  activeChunk: JamiyyahChunk | null;
  onSelectChunk: (chunkId: string) => void;
  onOpenInspector: (chunkId: string) => void;
}

export function MaktabahExplorer({
  books,
  activeChunk,
  onSelectChunk,
  onOpenInspector,
}: MaktabahExplorerProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [bookFilter, setBookFilter] = useState("");
  const [searchHits, setSearchHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showCleanArabic, setShowCleanArabic] = useState(false);

  async function executeSearch(q: string) {
    const trimmed = q.trim();
    if (!trimmed) {
      setSearchHits(null);
      setSearchError(null);
      return;
    }
    setSearching(true);
    setSearchError(null);
    try {
      const res = await searchChunks({
        q: trimmed,
        category: category || undefined,
        book: bookFilter || undefined,
        status: status || undefined,
        limit: 25,
      });
      setSearchHits(res.hits ?? []);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Gagal mencari");
    } finally {
      setSearching(false);
    }
  }

  useEffect(() => {
    if (searchQuery.trim()) {
      void executeSearch(searchQuery);
    } else {
      setSearchHits(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, status, bookFilter]);

  function handleSearchSubmit(e: FormEvent) {
    e.preventDefault();
    void executeSearch(searchQuery);
  }

  const filteredBooks = books.filter((b) => {
    if (category && b.source_category !== category) return false;
    if (bookFilter && b.title !== bookFilter) return false;
    return true;
  });

  const visibleEntriesCount = filteredBooks.reduce(
    (sum, book) =>
      sum +
      book.chapters.reduce(
        (cSum, chap) =>
          cSum +
          chap.items.filter((it) => !status || it.verification_status === status).length,
        0
      ),
    0
  );

  const counterText = searchHits !== null
    ? `${searchHits.length} hasil`
    : searching
    ? "Mencari..."
    : `${filteredBooks.length} kitab · ${visibleEntriesCount.toLocaleString("id-ID")} entri`;

  const matanArabic =
    typeof activeChunk?.metadata?.matan_arabic === "string"
      ? activeChunk.metadata.matan_arabic
      : null;
  const footnotes = activeChunk?.metadata?.footnotes ?? [];
  const referencedBooks = (activeChunk?.metadata?.referenced_books ?? [])
    .map((b) => (typeof b === "string" ? b : b.title))
    .filter(Boolean)
    .join(", ");

  const displayedArabic = activeChunk
    ? showCleanArabic
      ? activeChunk.content.arabic_clean || activeChunk.content.arabic_raw
      : activeChunk.content.arabic_raw || activeChunk.content.arabic_clean
    : "";

  return (
    <section className="tab-panel active" id="panel-maktabah" role="tabpanel">
      <div className="card maktabah-toolbar">
        <form className="search-box" onSubmit={handleSearchSubmit}>
          <input
            type="search"
            id="maktabah-search"
            value={searchQuery}
            onChange={(e) => {
              const val = e.target.value;
              setSearchQuery(val);
              if (!val.trim()) setSearchHits(null);
            }}
            placeholder="Cari fasal, istilah Arab, atau terjemah Indonesia..."
          />
          <button type="submit" className="btn-secondary" id="maktabah-search-btn">
            <Search size={15} />
            <span>Cari</span>
          </button>
        </form>

        <div className="filter-row">
          <select
            id="filter-category"
            className="select-compact"
            aria-label="Filter kategori sumber"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">Semua Kategori</option>
            <option value="kitab_turats">Kitab Turats</option>
            <option value="hadith">Hadits</option>
            <option value="bahtsul_masail">Bahtsul Masail</option>
            <option value="quran">Al-Qur'an</option>
          </select>

          <select
            id="filter-status"
            className="select-compact"
            aria-label="Filter status verifikasi"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">Semua Status</option>
            <option value="pending">pending</option>
            <option value="machine_verified">machine_verified</option>
            <option value="scholarly_verified">scholarly_verified</option>
            <option value="rejected">rejected</option>
          </select>

          <select
            id="filter-book"
            className="select-compact"
            aria-label="Filter kitab"
            value={bookFilter}
            onChange={(e) => setBookFilter(e.target.value)}
          >
            <option value="">Semua Kitab</option>
            {books.map((book) => (
              <option key={book.book_key} value={book.title}>
                {book.title} ({book.chunk_count.toLocaleString("id-ID")})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="maktabah-grid">
        <aside className="card maktabah-tree-col">
          <div className="panel-header">
            <h3>Daftar Kitab &amp; Bab</h3>
            <span className="mini-counter">{counterText}</span>
          </div>

          <div className="book-tree" id="book-tree">
            {searchError ? (
              <div className="sources-placeholder">Gagal mencari: {searchError}</div>
            ) : searchHits !== null ? (
              searchHits.length === 0 ? (
                <div className="sources-placeholder">
                  Tidak ada entri yang cocok dengan kata kunci tersebut.
                </div>
              ) : (
                <ul className="chunk-link-list">
                  {searchHits.map((hit) => {
                    const c = hit.chunk;
                    const title = c.hierarchy.join(" › ") || c.chunk_id;
                    return (
                      <li key={c.chunk_id}>
                        <button
                          type="button"
                          className={`chunk-link-btn ${
                            activeChunk?.chunk_id === c.chunk_id ? "active" : ""
                          }`}
                          onClick={() => onSelectChunk(c.chunk_id)}
                        >
                          <strong>{title}</strong>
                          <br />
                          <small>
                            {c.chunk_id} · skor {hit.rerank_score.toFixed(3)}
                          </small>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )
            ) : filteredBooks.length === 0 ? (
              <div className="sources-placeholder">
                {books.length === 0
                  ? "Memuat daftar kitab..."
                  : "Tidak ada kitab sesuai filter."}
              </div>
            ) : (
              filteredBooks.map((book, bIdx) => {
                const visibleChapters = book.chapters
                  .map((chap) => ({
                    ...chap,
                    filteredItems: chap.items.filter(
                      (it) => !status || it.verification_status === status
                    ),
                  }))
                  .filter((chap) => chap.filteredItems.length > 0);

                if (visibleChapters.length === 0) return null;

                return (
                  <details key={book.book_key} className="book-group" open={bIdx === 0}>
                    <summary className="book-summary">
                      <span>{book.title}</span>
                      <span className="book-count">
                        {book.chunk_count.toLocaleString("id-ID")}
                      </span>
                    </summary>

                    {visibleChapters.map((chap, cIdx) => (
                      <details
                        key={`${book.book_key}-${chap.title}`}
                        className="chapter-group"
                        open={bIdx === 0 && cIdx === 0}
                      >
                        <summary className="chapter-summary">
                          {chap.title} ({chap.chunk_count.toLocaleString("id-ID")})
                        </summary>
                        <ul className="chunk-link-list">
                          {chap.filteredItems.map((it) => (
                            <li key={it.chunk_id}>
                              <button
                                type="button"
                                className={`chunk-link-btn ${
                                  activeChunk?.chunk_id === it.chunk_id ? "active" : ""
                                }`}
                                onClick={() => onSelectChunk(it.chunk_id)}
                              >
                                {it.label || it.short_label || it.chunk_id}
                              </button>
                            </li>
                          ))}
                        </ul>
                      </details>
                    ))}
                  </details>
                );
              })
            )}
          </div>
        </aside>

        <section className="card maktabah-reader-col">
          {!activeChunk ? (
            <div className="empty-state compact">
              <h3>Pilih Fasal atau Hasil Pencarian</h3>
              <p>
                Telusuri <em>Matan al-Ghayah wat-Taqrib</em>, <em>Fathul Qarib</em>, korpus{" "}
                <em>Hadits</em>, dan <em>Bahtsul Masail</em> secara paralel antara teks Arab dan
                terjemahan.
              </p>
            </div>
          ) : (
            <article id="reader-content">
              <header className="reader-header">
                <div className="reader-breadcrumb">
                  {activeChunk.hierarchy.join(" › ") ||
                    activeChunk.citation.full_reference ||
                    activeChunk.chunk_id}
                </div>
                <div className="reader-badges">
                  <span className="badge badge-accent">{activeChunk.source_category}</span>
                  <span
                    className={`verif-badge verif-${
                      activeChunk.metadata.verification_status || "pending"
                    }`}
                  >
                    {activeChunk.metadata.verification_status || "pending"}
                  </span>
                  {activeChunk.metadata.madzhab && (
                    <span className="badge">{activeChunk.metadata.madzhab}</span>
                  )}
                </div>
              </header>

              <div className="reader-controls">
                <label className="toggle-chip">
                  <input
                    type="checkbox"
                    checked={showCleanArabic}
                    onChange={(e) => setShowCleanArabic(e.target.checked)}
                  />
                  <span>
                    Tampilkan <code>arabic_clean</code> (tanpa harakat)
                  </span>
                </label>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => onOpenInspector(activeChunk.chunk_id)}
                >
                  Lihat di Inspektor JSON →
                </button>
              </div>

              <div className="arabic-block" dir="rtl" lang="ar">
                {displayedArabic || "(Teks Arab tidak tersedia pada entri ini)"}
              </div>

              {matanArabic && (
                <div className="reader-section">
                  <h4>Matan Terkait (Syarah / Matan)</h4>
                  <div className="arabic-block matan-block" dir="rtl" lang="ar">
                    {matanArabic}
                  </div>
                </div>
              )}

              <div className="reader-section">
                <h4>Terjemahan / Keterangan Indonesia</h4>
                <div className="indonesian-block">
                  {activeChunk.content.indonesian ||
                    "(Belum tersedia terjemahan Indonesia pada entri ini.)"}
                </div>
              </div>

              {footnotes.length > 0 && (
                <div className="reader-section">
                  <h4>Catatan Kaki &amp; Tahqiq</h4>
                  <ul className="footnotes-list">
                    {footnotes.map((fn, idx) => (
                      <li key={idx}>{fn}</li>
                    ))}
                  </ul>
                </div>
              )}

              <footer className="reader-footer">
                <div>
                  <strong>Rujukan:</strong> {activeChunk.citation.full_reference || "—"}
                </div>
                <div>
                  <strong>Chunk ID:</strong> <code>{activeChunk.chunk_id}</code>
                  {referencedBooks && (
                    <>
                      {" · "}
                      <strong>Kitab Dirujuk:</strong> {referencedBooks}
                    </>
                  )}
                </div>
              </footer>
            </article>
          )}
        </section>
      </div>
    </section>
  );
}
