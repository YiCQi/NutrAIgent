"""Provider-independent LLM interface (BYOK).

Internal message format (Anthropic-like blocks):
  {"role": "user"|"assistant", "content": str | [block, ...]}
  block: {"type": "text", "text": str}
       | {"type": "tool_use", "id": str, "name": str, "input": dict}
       | {"type": "tool_result", "tool_use_id": str, "content": str}
Provider.complete() returns {"content": [text/tool_use blocks], "stop": "tool_use"|"end"}.
Adapters translate to/from each vendor API. Keys are never logged or put in error messages.
"""
import json
from dataclasses import dataclass

import httpx


class ProviderError(Exception):
    pass


@dataclass
class ProviderConfig:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""


class Provider:
    def __init__(self, cfg: ProviderConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self.timeout = 120  # seconds per request; long generations (meal plans) raise it
        self._client = httpx.Client(transport=transport)

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        raise NotImplementedError

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        try:
            r = self._client.post(url, headers=headers, json=payload, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"network error: {type(e).__name__}") from None
        if r.status_code >= 400:
            raise ProviderError(f"provider returned {r.status_code}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError:
            raise ProviderError("provider returned non-JSON response") from None


class AnthropicProvider(Provider):
    DEFAULT_URL = "https://api.anthropic.com"

    def complete(self, system, messages, tools):
        base = (self.cfg.base_url or self.DEFAULT_URL).rstrip("/")
        payload = {
            "model": self.cfg.model, "max_tokens": 2048, "system": system, "messages": messages,
        }
        if tools:
            payload["tools"] = [{"name": t["name"], "description": t["description"],
                                 "input_schema": t["parameters"]} for t in tools]
        data = self._post(f"{base}/v1/messages",
                          {"x-api-key": self.cfg.api_key, "anthropic-version": "2023-06-01"}, payload)
        content = []
        for b in data.get("content", []):
            if b.get("type") == "text":
                content.append({"type": "text", "text": b["text"]})
            elif b.get("type") == "tool_use":
                content.append({"type": "tool_use", "id": b["id"], "name": b["name"],
                                "input": b.get("input") or {}})
        stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "end"
        return {"content": content, "stop": stop}


class OpenAICompatProvider(Provider):
    """OpenAI Chat Completions format: OpenAI, OpenRouter, Ollama, LM Studio, DeepSeek, etc."""
    DEFAULT_URL = "https://api.openai.com/v1"

    @staticmethod
    def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
        out = [{"role": "system", "content": system}]
        for m in messages:
            c = m["content"]
            if isinstance(c, str):
                out.append({"role": m["role"], "content": c})
                continue
            if m["role"] == "assistant":
                text = "".join(b["text"] for b in c if b["type"] == "text")
                calls = [{"id": b["id"], "type": "function",
                          "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                         for b in c if b["type"] == "tool_use"]
                msg = {"role": "assistant", "content": text or None}
                if calls:
                    msg["tool_calls"] = calls
                out.append(msg)
            else:
                for b in c:
                    if b["type"] == "tool_result":
                        out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]})
                text = "".join(b["text"] for b in c if b["type"] == "text")
                if text:
                    out.append({"role": "user", "content": text})
        return out

    def complete(self, system, messages, tools):
        base = (self.cfg.base_url or self.DEFAULT_URL).rstrip("/")
        payload = {
            "model": self.cfg.model,
            "messages": self.to_openai_messages(system, messages),
        }
        if tools:  # some servers reject an empty tools array
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}
        data = self._post(f"{base}/chat/completions", headers, payload)
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise ProviderError("unexpected response shape") from None
        content = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            content.append({"type": "tool_use", "id": tc["id"], "name": tc["function"]["name"], "input": args})
        stop = "tool_use" if any(b["type"] == "tool_use" for b in content) else "end"
        return {"content": content, "stop": stop}


REGISTRY = {"anthropic": AnthropicProvider, "openai_compatible": OpenAICompatProvider}


def make_provider(cfg: ProviderConfig, transport=None) -> Provider:
    cls = REGISTRY.get(cfg.provider)
    if cls is None:
        raise ProviderError(f"unknown provider: {cfg.provider}")
    if not cfg.model:
        raise ProviderError("model not set")
    if cfg.provider == "anthropic" and not cfg.api_key:
        raise ProviderError("API key not set")
    return cls(cfg, transport)
