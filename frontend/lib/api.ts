export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type RepoSummary = {
  repo_id: string;
  name: string;
  source: string;
  source_type: "url" | "path";
  root_path: string;
  indexed_at: string | null;
  status: string;
  error: string | null;
};

export type FileNode = {
  path: string;
  kind: "file" | "directory";
  language?: string | null;
  children: FileNode[];
};

export type TraceStep = {
  file_path: string;
  symbol?: string | null;
  line_range: [number, number];
  summary: string;
};

export type Citation = {
  file_path: string;
  start_line: number;
  end_line: number;
  label?: string | null;
};

export type QueryMode = "overview" | "trace" | "diagram";

export type QueryResponse = {
  answer: string;
  mode: QueryMode;
  trace: TraceStep[];
  citations: Citation[];
  mermaid?: string | null;
  search_history: string[];
};

export type Hotspot = {
  file_path: string;
  imports_count: number;
  imported_by_count: number;
  symbols_count: number;
  score: number;
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return parseResponse<T>(response);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail ?? `Request failed with status ${response.status}`);
  }
  return payload as T;
}

