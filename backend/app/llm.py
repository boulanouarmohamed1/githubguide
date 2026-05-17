from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import Settings


class ChatUnavailable(RuntimeError):
    pass


class OllamaChat:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, system: str, user: str) -> str:
        try:
            return self._ollama_chat(system, user)
        except Exception as exc:
            if not self.settings.allow_fallback_chat:
                raise ChatUnavailable(
                    f"Ollama chat unavailable at {self.settings.ollama_base_url}: {exc}"
                ) from exc
            return fallback_completion(user)

    def _ollama_chat(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": self.settings.chat_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ChatUnavailable(str(exc)) from exc
        content = body.get("message", {}).get("content")
        if not content:
            raise ChatUnavailable(f"Ollama returned no message content: {body}")
        return content


def fallback_completion(prompt: str) -> str:
    lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    evidence = [line for line in lines if line.startswith("- ")]
    if not evidence:
        return "I could not reach the local chat model, but the retrieval layer completed. No evidence snippets were available."
    summary = "\n".join(evidence[:8])
    return (
        "I could not reach the local chat model, so this is an extractive summary from retrieved evidence.\n\n"
        f"{summary}"
    )

