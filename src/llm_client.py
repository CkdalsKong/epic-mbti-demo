"""
Unified LLM client: Claude API | vLLM | Ollama
Set LLM_BACKEND env var to switch.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LLM_BACKEND, CLAUDE_MODEL, CLAUDE_API_KEY,
    VLLM_URL, VLLM_MODEL, OLLAMA_MODEL,
)


def call_llm(
    messages: list[dict],
    system: str = "You are a helpful assistant.",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    backend: str | None = None,
) -> str:
    backend = backend or LLM_BACKEND
    if backend == "claude":
        return _call_claude(messages, system, max_tokens, temperature)
    elif backend == "vllm":
        return _call_vllm(messages, system, max_tokens, temperature)
    elif backend == "ollama":
        return _call_ollama(messages, system, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {backend}")


def _call_claude(messages, system, max_tokens, temperature) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


def _call_vllm(messages, system, max_tokens, temperature) -> str:
    import requests
    payload = {
        "model": VLLM_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        # Disable Qwen3 thinking mode for fast filtering
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(f"{VLLM_URL}/chat/completions", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_ollama(messages, system, max_tokens, temperature) -> str:
    import requests
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    r = requests.post("http://localhost:11434/api/chat", json=payload, timeout=180)
    r.raise_for_status()
    return r.json()["message"]["content"]
