from __future__ import annotations

import re
from typing import NotRequired, TypedDict

from app.agent.prompts import SYSTEM_PROMPT
from app.config import Settings
from app.llm import OllamaChat
from app.models import Citation, QueryMode, QueryResponse, TraceStep
from app.retrieval.tools import CodebaseTools, SearchResult
from app.storage import SQLiteStore


class AgentState(TypedDict):
    repo_id: str
    user_query: str
    mode: QueryMode
    context_stack: list[str]
    search_history: list[str]
    trace_steps: list[TraceStep]
    open_files: list[str]
    citations: list[Citation]
    evidence: list[SearchResult]
    diagram_requested: bool
    final_answer: NotRequired[str]
    mermaid: NotRequired[str | None]


class GithubGuideAgent:
    def __init__(self, settings: Settings, store: SQLiteStore, tools: CodebaseTools, chat: OllamaChat):
        self.settings = settings
        self.store = store
        self.tools = tools
        self.chat = chat
        self.graph = self._compile_graph()

    def run(self, query: str, mode: QueryMode) -> QueryResponse:
        initial: AgentState = {
            "repo_id": self.tools.repo_id,
            "user_query": query,
            "mode": mode,
            "context_stack": [],
            "search_history": [],
            "trace_steps": [],
            "open_files": [],
            "citations": [],
            "evidence": [],
            "diagram_requested": mode == "diagram",
        }
        if self.graph is not None:
            state = self.graph.invoke(initial)
        else:
            state = self._summarizer(self._explorer(self._architect(initial)))
        return QueryResponse(
            answer=state.get("final_answer", ""),
            mode=mode,
            trace=state["trace_steps"],
            citations=state["citations"],
            mermaid=state.get("mermaid"),
            search_history=state["search_history"],
        )

    def _compile_graph(self):
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None
        graph = StateGraph(AgentState)
        graph.add_node("architect", self._architect)
        graph.add_node("explorer", self._explorer)
        graph.add_node("summarizer", self._summarizer)
        graph.set_entry_point("architect")
        graph.add_edge("architect", "explorer")
        graph.add_edge("explorer", "summarizer")
        graph.add_edge("summarizer", END)
        return graph.compile()

    def _architect(self, state: AgentState) -> AgentState:
        query = state["user_query"]
        mode = state["mode"]
        search_terms = [query]
        if mode == "overview":
            search_terms.extend(["README project structure configuration entrypoint", "main app routes services"])
        elif mode == "diagram":
            search_terms.extend([f"{query} route controller service model", f"{query} sequence flow"])
        else:
            search_terms.extend([f"{query} route service database", f"{query} handler manager model"])
        state["search_history"] = dedupe(search_terms)
        return state

    def _explorer(self, state: AgentState) -> AgentState:
        evidence: list[SearchResult] = []
        for term in state["search_history"]:
            evidence.extend(self.tools.search_codebase(term))
        evidence = dedupe_results(evidence)

        discovered_symbols = []
        for result in evidence[:5]:
            discovered_symbols.extend(result.symbols)
            discovered_symbols.extend(extract_called_symbols(result.text))
        for symbol in dedupe(discovered_symbols)[:12]:
            definitions = self.tools.get_symbol_definition(symbol)
            evidence.extend(definitions)

        evidence = dedupe_results(evidence)
        state["evidence"] = evidence
        state["open_files"] = dedupe([result.file_path for result in evidence])
        state["context_stack"] = state["open_files"][:8]
        state["citations"] = [
            Citation(
                file_path=result.file_path,
                start_line=result.start_line,
                end_line=result.end_line,
                label=", ".join(result.symbols) if result.symbols else None,
            )
            for result in evidence[:10]
        ]
        state["trace_steps"] = [
            TraceStep(
                file_path=result.file_path,
                symbol=result.symbols[0] if result.symbols else None,
                line_range=(result.start_line, result.end_line),
                summary=summarize_chunk(result),
            )
            for result in evidence[:8]
        ]
        return state

    def _summarizer(self, state: AgentState) -> AgentState:
        evidence_lines = []
        for result in state["evidence"][:10]:
            symbol = f" symbols={','.join(result.symbols)}" if result.symbols else ""
            snippet = compact(result.text)
            evidence_lines.append(
                f"- {result.file_path}:{result.start_line}-{result.end_line}{symbol}: {snippet}"
            )
        user_prompt = (
            f"Question: {state['user_query']}\n"
            f"Mode: {state['mode']}\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
            + "\n\nReturn a concise walkthrough with file names and line numbers."
        )
        answer = self.chat.complete(SYSTEM_PROMPT, user_prompt)
        state["final_answer"] = answer
        if state["diagram_requested"]:
            state["mermaid"] = build_mermaid(state["trace_steps"])
        else:
            state["mermaid"] = None
        return state


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def dedupe_results(results: list[SearchResult]) -> list[SearchResult]:
    seen = set()
    output = []
    for result in sorted(results, key=lambda item: item.score, reverse=True):
        key = (result.file_path, result.start_line, result.end_line)
        if key in seen:
            continue
        seen.add(key)
        output.append(result)
    return output


def extract_called_symbols(text: str) -> list[str]:
    symbols = re.findall(r"\b([A-Z][A-Za-z0-9_]+|[a-z_][A-Za-z0-9_]+)\s*\(", text)
    ignored = {"if", "for", "while", "return", "print", "len", "str", "int", "dict", "list"}
    return [symbol for symbol in symbols if symbol not in ignored]


def summarize_chunk(result: SearchResult) -> str:
    target = result.symbols[0] if result.symbols else "module code"
    return f"Inspect {target} in {result.file_path}:{result.start_line}-{result.end_line}."


def compact(text: str, limit: int = 420) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3] + "..."


def build_mermaid(trace_steps: list[TraceStep]) -> str:
    if not trace_steps:
        return "sequenceDiagram\n    participant User\n    participant Code\n    User->>Code: No trace evidence found"
    participants = []
    for step in trace_steps:
        name = participant_name(step.file_path)
        if name not in participants:
            participants.append(name)
    lines = ["sequenceDiagram"]
    for name in participants[:8]:
        lines.append(f"    participant {name}")
    for left, right in zip(trace_steps, trace_steps[1:]):
        left_name = participant_name(left.file_path)
        right_name = participant_name(right.file_path)
        label = right.symbol or "calls into"
        lines.append(f"    {left_name}->>{right_name}: {label}")
    first = participant_name(trace_steps[0].file_path)
    lines.insert(1, "    participant User")
    lines.append(f"    User->>{first}: {trace_steps[0].symbol or 'entry point'}")
    return "\n".join(lines)


def participant_name(path: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", path.split("/")[-1].split(".")[0])
    return cleaned or "Code"

