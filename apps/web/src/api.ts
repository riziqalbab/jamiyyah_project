import type {
  AskResponse,
  BookSummary,
  HealthResponse,
  JamiyyahChunk,
  SearchResponse,
} from "./types";

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const data = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiJson<HealthResponse>("/api/health");
}

export async function fetchBooks(): Promise<BookSummary[]> {
  const data = await apiJson<{ books: BookSummary[] }>("/api/books");
  return data.books ?? [];
}

export function fetchChunk(chunkId: string): Promise<JamiyyahChunk> {
  return apiJson<JamiyyahChunk>(`/api/chunk/${encodeURIComponent(chunkId)}`);
}

export function searchChunks(params: {
  q: string;
  category?: string;
  book?: string;
  status?: string;
  limit?: number;
}): Promise<SearchResponse> {
  const qs = new URLSearchParams({
    q: params.q,
    limit: String(params.limit ?? 25),
  });
  if (params.category) qs.set("category", params.category);
  if (params.book) qs.set("book", params.book);
  if (params.status) qs.set("status", params.status);
  return apiJson<SearchResponse>(`/api/search?${qs.toString()}`);
}

export function askQuestion(payload: {
  query: string;
  min_score: number;
  category: string | null;
}): Promise<AskResponse> {
  return apiJson<AskResponse>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
