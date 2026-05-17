"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bot,
  Braces,
  Code2,
  FolderGit2,
  Loader2,
  PanelRightOpen,
  Play,
  Search,
  Send,
  Sparkles
} from "lucide-react";
import { FileTree } from "@/components/FileTree";
import { MermaidBlock } from "@/components/MermaidBlock";
import {
  apiGet,
  apiPost,
  type FileNode,
  type Hotspot,
  type QueryMode,
  type QueryResponse,
  type RepoSummary
} from "@/lib/api";

type IngestResponse = {
  repo: RepoSummary;
  files_indexed: number;
  chunks_indexed: number;
  symbols_indexed: number;
};

type FileContent = {
  path: string;
  content: string;
  language?: string | null;
  line_count: number;
};

export default function Home() {
  const [repos, setRepos] = useState<RepoSummary[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [source, setSource] = useState("");
  const [sourceType, setSourceType] = useState<"auto" | "url" | "path">("auto");
  const [tree, setTree] = useState<FileNode[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<FileContent | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [query, setQuery] = useState("Give me an overview of the project structure.");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [mode, setMode] = useState<QueryMode>("overview");
  const [answer, setAnswer] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedRepo = useMemo(
    () => repos.find((repo) => repo.repo_id === selectedRepoId) ?? null,
    [repos, selectedRepoId]
  );

  useEffect(() => {
    refreshRepos();
  }, []);

  useEffect(() => {
    if (!selectedRepoId) return;
    setSelectedPath(null);
    setFileContent(null);
    apiGet<FileNode[]>(`/api/repos/${selectedRepoId}/tree`).then(setTree).catch(showError);
    apiGet<Hotspot[]>(`/api/repos/${selectedRepoId}/hotspots`).then(setHotspots).catch(showError);
  }, [selectedRepoId]);

  async function refreshRepos() {
    try {
      const nextRepos = await apiGet<RepoSummary[]>("/api/repos");
      setRepos(nextRepos);
      setSelectedRepoId((current) => current ?? nextRepos[0]?.repo_id ?? null);
    } catch (err) {
      showError(err);
    }
  }

  function showError(err: unknown) {
    setError(err instanceof Error ? err.message : String(err));
  }

  async function ingest() {
    setError(null);
    setLoading("ingest");
    try {
      const payload = {
        source,
        source_type: sourceType === "auto" ? null : sourceType,
        reindex: true
      };
      const result = await apiPost<IngestResponse>("/api/repos/ingest", payload);
      await refreshRepos();
      setSelectedRepoId(result.repo.repo_id);
      setSource("");
    } catch (err) {
      showError(err);
    } finally {
      setLoading(null);
    }
  }

  async function openFile(path: string) {
    if (!selectedRepoId) return;
    setSelectedPath(path);
    setError(null);
    try {
      const content = await apiGet<FileContent>(
        `/api/repos/${selectedRepoId}/files/content?path=${encodeURIComponent(path)}`
      );
      setFileContent(content);
    } catch (err) {
      showError(err);
    }
  }

  async function ask() {
    if (!selectedRepoId || !query.trim()) return;
    setError(null);
    setLoading("query");
    setSubmittedQuery(query);
    try {
      const response = await apiPost<QueryResponse>(`/api/repos/${selectedRepoId}/query`, { query, mode });
      setAnswer(response);
    } catch (err) {
      showError(err);
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="chat-shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="mark">
            <Sparkles size={18} />
          </div>
          <div>
            <h1>GithubGuide</h1>
            <p>{selectedRepo?.name ?? "No repo selected"}</p>
          </div>
        </div>

        <section className="rail-section">
          <div className="section-label">
            <FolderGit2 size={15} />
            <span>Ingest</span>
          </div>
          <div className="ingest-box">
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="GitHub URL or local path"
            />
            <button className="send-small" onClick={ingest} disabled={!source || loading === "ingest"} title="Ingest">
              {loading === "ingest" ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
            </button>
          </div>
          <div className="segmented compact">
            {(["auto", "url", "path"] as const).map((item) => (
              <button key={item} className={sourceType === item ? "selected" : ""} onClick={() => setSourceType(item)}>
                {item}
              </button>
            ))}
          </div>
        </section>

        <section className="rail-section rail-scroll">
          <div className="section-label">
            <Search size={15} />
            <span>Repos</span>
          </div>
          <div className="repo-list">
            {repos.map((repo) => (
              <button
                key={repo.repo_id}
                className={selectedRepoId === repo.repo_id ? "repo active" : "repo"}
                onClick={() => setSelectedRepoId(repo.repo_id)}
              >
                <span>{repo.name}</span>
                <small>{repo.status}</small>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <section className="conversation">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Local agentic RAG</p>
            <h2>{selectedRepo ? selectedRepo.name : "Choose or ingest a repository"}</h2>
          </div>
          <div className="mode-switch">
            {(["overview", "trace", "diagram"] as QueryMode[]).map((item) => (
              <button key={item} className={mode === item ? "selected" : ""} onClick={() => setMode(item)}>
                {item}
              </button>
            ))}
          </div>
        </header>

        {error && <div className="error">{error}</div>}

        <div className="messages">
          {!answer && !submittedQuery && (
            <div className="empty-state">
              <div className="empty-mark">
                <Bot size={26} />
              </div>
              <h3>Ask about the codebase</h3>
              <p>Trace flows, summarize structure, or generate a Mermaid sequence from indexed code.</p>
            </div>
          )}

          {submittedQuery && (
            <article className="message user-message">
              <div className="bubble">{submittedQuery}</div>
            </article>
          )}

          {(answer || loading === "query") && (
            <article className="message assistant-message">
              <div className="avatar">
                {loading === "query" ? <Loader2 size={17} className="spin" /> : <Sparkles size={17} />}
              </div>
              <div className="assistant-body">
                {loading === "query" ? (
                  <p className="thinking">Tracing the repo...</p>
                ) : (
                  answer && (
                    <>
                      <p>{answer.answer}</p>
                      {answer.mermaid && <MermaidBlock chart={answer.mermaid} />}
                      <div className="evidence-grid">
                        <section>
                          <h3>Trace</h3>
                          <div className="trace-list">
                            {answer.trace.map((step) => (
                              <button
                                key={`${step.file_path}-${step.line_range[0]}`}
                                onClick={() => openFile(step.file_path)}
                              >
                                <Braces size={15} />
                                <span>
                                  {step.file_path}:{step.line_range[0]}-{step.line_range[1]}
                                </span>
                              </button>
                            ))}
                          </div>
                        </section>
                        <section>
                          <h3>Citations</h3>
                          <div className="citation-list">
                            {answer.citations.map((citation) => (
                              <button
                                key={`${citation.file_path}-${citation.start_line}`}
                                onClick={() => openFile(citation.file_path)}
                              >
                                {citation.file_path}:{citation.start_line}-{citation.end_line}
                              </button>
                            ))}
                          </div>
                        </section>
                      </div>
                    </>
                  )
                )}
              </div>
            </article>
          )}
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  ask();
                }
              }}
              placeholder="Ask how a flow works..."
            />
            <button className="send-button" onClick={ask} disabled={!selectedRepoId || loading === "query"}>
              {loading === "query" ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </section>

      <aside className="context-panel">
        <div className="context-header">
          <div>
            <p className="eyebrow">Context</p>
            <h2>{fileContent?.path ?? "Files and hotspots"}</h2>
          </div>
          <PanelRightOpen size={18} />
        </div>

        <section className="context-section">
          <div className="section-label">
            <Code2 size={15} />
            <span>Files</span>
          </div>
          <FileTree nodes={tree} selectedPath={selectedPath} onSelect={openFile} />
        </section>

        <section className="context-section context-code">
          {fileContent ? (
            <pre className="code-view">{fileContent.content}</pre>
          ) : (
            <div className="hotspots">
              {hotspots.map((hotspot) => (
                <button key={hotspot.file_path} onClick={() => openFile(hotspot.file_path)}>
                  <span>{hotspot.file_path}</span>
                  <small>score {hotspot.score}</small>
                </button>
              ))}
            </div>
          )}
        </section>
      </aside>
    </main>
  );
}

