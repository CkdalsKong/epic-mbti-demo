#!/usr/bin/env python3
"""
EPIC Demo Server — extends epic_runtime with /generate and /evaluate.
Endpoints:
  GET  /health     → server status
  POST /run        → stream EPIC indexing events (ndjson), stores session state
  POST /generate   → stream generation from EPIC-RAG and plain-RAG (ndjson)
  POST /evaluate   → 4-metric preference following evaluation (JSON)
"""

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import faiss
import numpy as np

os_environ_set = __import__("os").environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from epic_runtime import (
    CONTRIEVER_MODEL,
    VLLM_MODEL,
    VLLM_SERVER_URL,
    ContrieverEncoder,
    build_index,
    run_pipeline,
)

# ── Defaults for the H200 setup ────────────────────────────────────────────
DEMO_VLLM_MODEL = "Qwen/Qwen3-8B"
DEMO_VLLM_URL = "http://127.0.0.1:8008"

# ── Evaluation prompts ─────────────────────────────────────────────────────
EVAL_SYSTEM = (
    "You are a helpful assistant in evaluating an AI assistant's response. "
    "You should be fair and strict and follow the user's instruction."
)

ACKNOW_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant acknowledges any user preference in answering the user's query.

Evaluate the response based on these stringent criteria:

1. Check if the response explicitly or implicitly mentions or references a user preference. 2. The content of the preference is irrelevant for this check; only its presence matters.

Answer "Yes" if:

1. The response explicitly mentions or refers to a user preference in answering the user's question. Examples include: "Based on your previous preference for xxxx"; "Based on your previous preference, I would suggest you xxxx"; "Since you mentioned you prefer/dislike xxxx"; "Since you are a xxxx"; "I will recommend the following given your preference for xxx", etc. You should extract the "xxxx" in your answer. If it only says "Based on our previous conversation, I recommend..." and does not explicitly mention any preference, you should answer 'No'.
2. The response assumes the user preference in answering the user's question implicitly. For example, when the user asks 'Can you recommend me cars to drive?', if the response is 'Based on your preference, I will recommend non-EV cars, ...', then this indicates the assistant assumes that the user's preference is a dislike of EV cars, and you should answer 'Yes'.

Answer "No" if the response does not mention or refer to any user preference explicitly or implicitly. If you cannot extract the sentence stating what the preference is, answer 'No'.

Here is the assistant's response:
The user's question is: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Please answer in this exact XML format without any additional text:
<preference>[quote of the sentence that acknowledges/mentions what the preference is; leave it blank if there is none]</preference>
<answer>[Yes/No]</answer>"""

VIOLATE_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's response violates the user's stated preference.
Evaluate the response based on these criteria:

Answer "Yes" if:

1. The response contains any recommendations that directly contradict or violate the user's stated preference without any reasoning for why it recommends these contrasting items and no acknowledgment of the user's preference at all.

Answer "No" if:

1. The response respects the user's stated preference.
2. It's acceptable if it includes options that could potentially conflict with the preference, as long as it has acknowledged the user's preference and also specified the reason why or how to avoid the conflict.
3. If the response does not acknowledge the user's preference and if no recommendations violate the user's preference, there is no violation.

Here is the conversation:
User's preference: {preference}
User query: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

HALLUCINATE_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's restatement of the user's stated preference is the same preference. Evaluate the response based on these stringent criteria to answer if the assistant has hallucinated the preference or not:

Answer "Yes" if:

1. The assistant's restatement differs from the original preference in meaning or intent.
2. The assistant's restatement contradicts the original preference.
3. The assistant's restatement is not related or irrelevant to the original preference.

Answer "No" if has not hallucinated:

1. The assistant's restatement matches the original preference.
2. The assistant's restatement is a minor paraphrase that fully preserves the meaning and intent of the original preference.
3. The restatement is just empty, no hallucination.

Here is the information:
Original user preference: "{preference}"
Assistant's restatement: "{assistant_restatement}"
Examine the original preference and the assistant's restatement meticulously and answer. Please answer in this exact XML format without any other additional text:
<explanation>[1 short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

HELPFUL_PROMPT = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant provides any substantive response to the user's query.
Evaluate the response based on these stringent criteria:

Answer "Yes" if any of the following:

1. The response provides specific, relevant recommendations or advice related to the user's query without any apologetic statements or claims of inability to respond.
2. It remembers the user's preference and provides recommendations or suggestions to the user's query without any apologetic statements or claims of inability to respond.

Answer "No" if any of the following:

1. The response contains apologetic statements or claims of inability to respond due to lack of memory of the user's preference.
2. The assistant asks for more information without providing any substantive suggestions, advices directly related to the query.
3. The response doesn't address the user's query.
4. Even if the agent provides some relevant recommendations, if the agent first expresses an inability to follow the user's preference, answer 'No'.

Here is the conversation:
User query: {question}
Assistant response: {end_generation}

Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

EPIC_GEN_SYSTEM = (
    "You are a helpful assistant. Answer the question using the retrieved documents below. "
    "Give a thorough, practical response with specific advice. Use 3-5 paragraphs."
)

RAG_GEN_SYSTEM = (
    "You are a helpful assistant. Answer the question using the retrieved documents below. "
    "Give a thorough, practical response with specific advice. Use 3-5 paragraphs."
)


# ── Session state ─────────────────────────────────────────────────────────

class DemoSession:
    def __init__(self):
        self.session_id: str = ""
        # EPIC retrieval structures
        self.epic_index: faiss.IndexFlatIP | None = None
        self.epic_entries: list[dict[str, Any]] = []  # {chunk_text, article_title, instruction, preference}
        self.epic_index_bytes: int = 0
        # RAG retrieval structures
        self.rag_index: faiss.IndexFlatIP | None = None
        self.rag_chunks: list[dict[str, Any]] = []   # {chunk_text, article_title}
        self.rag_index_bytes: int = 0
        # All preferences (for eval query)
        self.preferences: list[str] = []
        # Cached preference embeddings, aligned to self.preferences — used to
        # steer the query vector toward the persona's top-matching preference
        # before searching the EPIC instruction index.
        self.preference_vectors: np.ndarray | None = None


class EPICDemoState:
    def __init__(
        self,
        encoder: ContrieverEncoder,
        llm_model: str,
        llm_server_url: str,
        llm_timeout: int,
        eval_llm_model: str = "",
        eval_llm_server_url: str = "",
        preindex_dir: str = "",
    ):
        self.encoder = encoder
        self.llm_model = llm_model                          # indexing LLM (Qwen3-8B)
        self.llm_server_url = llm_server_url.rstrip("/")
        self.llm_timeout = llm_timeout
        # Evaluation LLM (Llama 70B) — falls back to indexing LLM if not set
        self.eval_llm_model = eval_llm_model or llm_model
        self.eval_llm_server_url = (eval_llm_server_url or llm_server_url).rstrip("/")
        # Pre-indexed persona directory
        self.preindex_dir = preindex_dir
        self._session: DemoSession | None = None
        self._lock = threading.Lock()

    @property
    def session(self) -> DemoSession | None:
        with self._lock:
            return self._session

    @session.setter
    def session(self, value: DemoSession) -> None:
        with self._lock:
            self._session = value

    def health_payload(self) -> dict[str, Any]:
        sess = self.session
        return {
            "ready": True,
            "embedding_model": CONTRIEVER_MODEL,
            "embedding_dimension": self.encoder.dimension,
            "index_llm": f"{self.llm_model} via vLLM",
            "eval_llm": f"{self.eval_llm_model} via vLLM",
            "llm_server_url": self.llm_server_url,
            "eval_llm_server_url": self.eval_llm_server_url,
            "session_ready": sess is not None,
            "session_id": sess.session_id if sess else None,
            "epic_entries": len(sess.epic_entries) if sess else 0,
            "epic_index_bytes": sess.epic_index_bytes if sess else 0,
            "rag_chunks": len(sess.rag_chunks) if sess else 0,
            "rag_index_bytes": sess.rag_index_bytes if sess else 0,
        }


# ── LLM helpers ───────────────────────────────────────────────────────────

def _chat_completions(
    state: EPICDemoState,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.3,
    stream: bool = False,
    extra_body: dict | None = None,
) -> Any:
    payload: dict[str, Any] = {
        "model": state.llm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if extra_body:
        payload.update(extra_body)
    url = f"{state.llm_server_url}/v1/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    return urllib.request.urlopen(req, timeout=state.llm_timeout)


def _generate_full(state: EPICDemoState, system: str, user: str) -> str:
    """Generate a full response (no streaming)."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    with _chat_completions(state, messages, max_tokens=1024, temperature=0.3) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _generate_streaming(
    state: EPICDemoState,
    system: str,
    user: str,
    event_prefix: str,
    emit: Any,
) -> str:
    """Generate with streaming; emits {event: event_prefix+"_token", text: "..."} events."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    full_text = ""
    with _chat_completions(state, messages, max_tokens=1024, temperature=0.3, stream=True) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            chunk_data = line[6:]
            if chunk_data == "[DONE]":
                break
            try:
                chunk = json.loads(chunk_data)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    full_text += delta
                    emit(event_prefix + "_token", text=delta)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
    return full_text


def _eval_llm(state: EPICDemoState, prompt: str) -> str:
    messages = [
        {"role": "system", "content": EVAL_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    with _chat_completions(
        state, messages, max_tokens=300, temperature=0.0,
        extra_body={"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    ) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _gen_chat_completions(
    state: EPICDemoState,
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.3,
    stream: bool = False,
) -> Any:
    """Use the generation LLM (Llama 70B) instead of the indexing LLM."""
    payload: dict[str, Any] = {
        "model": state.eval_llm_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    url = f"{state.eval_llm_server_url}/v1/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    return urllib.request.urlopen(req, timeout=state.llm_timeout)


def _gen_streaming(
    state: EPICDemoState,
    system: str,
    user: str,
    event_prefix: str,
    emit: Any,
) -> str:
    """Generate with generation LLM, streaming tokens."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    full_text = ""
    with _gen_chat_completions(state, messages, max_tokens=1024, temperature=0.3, stream=True) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            chunk_data = line[6:]
            if chunk_data == "[DONE]":
                break
            try:
                chunk = json.loads(chunk_data)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    full_text += delta
                    emit(event_prefix + "_token", text=delta)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
    return full_text


# ── Evaluation ────────────────────────────────────────────────────────────

def _parse_answer(text: str) -> str:
    m = re.search(r"<answer>\s*([^\s<]+)\s*</answer>", text, re.IGNORECASE)
    return m.group(1).strip().lower() if m else ""


def _parse_preference(text: str) -> str:
    m = re.search(r"<preference>(.*?)</preference>", text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def evaluate_single(state: EPICDemoState, question: str, preference: str, response: str) -> dict:
    def run_acknow():
        p = ACKNOW_PROMPT.format(question=question, end_generation=response)
        raw = _eval_llm(state, p)
        return "acknow", {"answer": _parse_answer(raw), "extract_pref": _parse_preference(raw), "raw": raw}

    def run_violate():
        p = VIOLATE_PROMPT.format(preference=preference, question=question, end_generation=response)
        raw = _eval_llm(state, p)
        return "violate", {"answer": _parse_answer(raw), "raw": raw}

    def run_helpful():
        p = HELPFUL_PROMPT.format(question=question, end_generation=response)
        raw = _eval_llm(state, p)
        return "helpful", {"answer": _parse_answer(raw), "raw": raw}

    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        for k, v in ex.map(lambda fn: fn(), [run_acknow, run_violate, run_helpful]):
            results[k] = v

    is_acknowledgement = "yes" in results.get("acknow", {}).get("answer", "")
    if is_acknowledgement:
        extract_pref = results["acknow"].get("extract_pref", "")
        p = HALLUCINATE_PROMPT.format(preference=preference, assistant_restatement=extract_pref)
        raw = _eval_llm(state, p)
        results["hallucinate"] = {"answer": _parse_answer(raw), "raw": raw}
    else:
        results["hallucinate"] = {"answer": "no", "raw": ""}

    is_violation = "yes" in results.get("violate", {}).get("answer", "")
    is_hallucinate = is_acknowledgement and "yes" in results.get("hallucinate", {}).get("answer", "")
    is_unhelpful = "no" in results.get("helpful", {}).get("answer", "")

    is_inconsistent = is_acknowledgement and not is_hallucinate and is_violation and not is_unhelpful
    is_halluc_violation = is_acknowledgement and is_hallucinate and is_violation and not is_unhelpful
    is_unaware_violation = not is_acknowledgement and is_violation and not is_unhelpful

    preference_following = not any([is_inconsistent, is_halluc_violation, is_unaware_violation, is_unhelpful])

    return {
        "acknow": is_acknowledgement,
        "violate": is_violation,
        "hallucinate": is_hallucinate,
        "helpful": not is_unhelpful,
        "preference_following": preference_following,
    }


# ── Retrieval ─────────────────────────────────────────────────────────────

def load_persona_session(state: "EPICDemoState", persona_index: int) -> DemoSession:
    """Load a pre-built persona index from disk (built by preindex_corpus.py).
    Shared by the /load_persona HTTP handler and offline scripts (curate_qa.py)
    that need a session without going through the server."""
    if not state.preindex_dir:
        raise RuntimeError("Server/state was not configured with a preindex_dir.")

    persona_dir = os.path.join(state.preindex_dir, f"persona_{persona_index}")
    meta_path = os.path.join(persona_dir, "meta.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(
            f"No pre-indexed data for persona {persona_index}. "
            f"Run preindex_corpus.py first. (looked in {persona_dir})"
        )

    with open(meta_path) as f:
        meta = json.load(f)

    epic_index = faiss.read_index(os.path.join(persona_dir, "epic_index.faiss"))
    with open(os.path.join(persona_dir, "epic_entries.json")) as f:
        epic_entries_raw = json.load(f)
    epic_entries = [
        {
            "chunk_text": e["chunk_text"],
            "article_title": e["article_title"],
            "instruction": e.get("instruction", ""),
            "preference": e.get("preference", ""),
        }
        for e in epic_entries_raw
    ]

    # RAG index is shared across personas — prefer the path stored in meta
    rag_index_path = meta.get("rag_index_path") or os.path.join(persona_dir, "rag_index.faiss")
    rag_chunks_path = meta.get("rag_chunks_path") or os.path.join(persona_dir, "rag_chunks.json")
    rag_index = faiss.read_index(rag_index_path)
    with open(rag_chunks_path) as f:
        rag_chunks = json.load(f)

    session = DemoSession()
    session.session_id = str(uuid.uuid4())
    session.epic_index = epic_index
    session.epic_entries = epic_entries
    session.epic_index_bytes = meta.get("epic_index_bytes", 0)
    session.rag_index = rag_index
    session.rag_chunks = rag_chunks
    session.rag_index_bytes = meta.get("rag_index_bytes", 0)
    session.preferences = meta.get("preferences", [])
    session.preference_vectors = (
        state.encoder.encode(session.preferences) if session.preferences else None
    )
    return session


def epic_steer_query(session: DemoSession, q_vec: np.ndarray) -> tuple[np.ndarray, str | None, float]:
    """EPIC query steering: compare the query to the persona's preference
    embeddings, take the top-1 match, and fold it into the query vector
    before searching the instruction index. Returns (steered_vec, matched
    preference text, match score). Falls back to the raw query vector if
    there are no cached preference embeddings.
    """
    if session.preference_vectors is None or session.preference_vectors.shape[0] == 0:
        return q_vec, None, 0.0
    sims = session.preference_vectors @ q_vec[0]          # (P,)
    top_idx = int(np.argmax(sims))
    top_pref_vec = session.preference_vectors[top_idx]
    steered = q_vec[0] + top_pref_vec
    norm = np.linalg.norm(steered)
    if norm > 0:
        steered = steered / norm
    steered_vec = steered.reshape(1, -1).astype("float32")
    matched_pref = session.preferences[top_idx] if top_idx < len(session.preferences) else None
    return steered_vec, matched_pref, float(sims[top_idx])


def epic_search(session: DemoSession, q_vec: np.ndarray, top_k: int = 5) -> list[dict]:
    """Search the EPIC instruction index given an already-computed query vector."""
    if session.epic_index is None or session.epic_index.ntotal == 0:
        return []
    scores, indices = session.epic_index.search(q_vec, min(top_k, session.epic_index.ntotal))
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(session.epic_entries):
            continue
        entry = dict(session.epic_entries[idx])
        entry["score"] = float(score)
        results.append(entry)
    return results


def rag_search(session: DemoSession, q_vec: np.ndarray, top_k: int = 5) -> list[dict]:
    """Search the RAG chunk index given an already-computed query vector."""
    if session.rag_index is None or session.rag_index.ntotal == 0:
        return []
    scores, indices = session.rag_index.search(q_vec, min(top_k, session.rag_index.ntotal))
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(session.rag_chunks):
            continue
        chunk = dict(session.rag_chunks[idx])
        chunk["score"] = float(score)
        results.append(chunk)
    return results


def epic_retrieve(state: EPICDemoState, session: DemoSession, question: str, top_k: int = 5) -> list[dict]:
    q_vec = state.encoder.encode([question])
    steered_vec, _, _ = epic_steer_query(session, q_vec)
    return epic_search(session, steered_vec, top_k)


def rag_retrieve(state: EPICDemoState, session: DemoSession, question: str, top_k: int = 5) -> list[dict]:
    q_vec = state.encoder.encode([question])
    return rag_search(session, q_vec, top_k)


def build_epic_context(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs):
        guidance = doc.get("instruction", "")
        text = doc.get("chunk_text", "")
        src = doc.get("article_title", "")
        parts.append(f"[Doc {i+1}] ({src})\nGuidance: {guidance}\nContent: {text}")
    return "\n\n".join(parts)


def build_rag_context(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs):
        text = doc.get("chunk_text", "")
        src = doc.get("article_title", "")
        parts.append(f"[Doc {i+1}] ({src})\n{text}")
    return "\n\n".join(parts)


# ── HTTP server ───────────────────────────────────────────────────────────

class EPICDemoHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr: tuple, handler: type, state: EPICDemoState):
        super().__init__(addr, handler)
        self.state = state


class EPICDemoHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ── routing ──────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self.write_json(self.server.state.health_payload())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = self.path.rstrip("/")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self.write_json({"error": f"Bad JSON: {e}"}, 400)
            return

        if path == "/run":
            self.handle_run(payload)
        elif path == "/load_persona":
            self.handle_load_persona(payload)
        elif path == "/curated_questions":
            self.handle_curated_questions(payload)
        elif path == "/retrieve":
            self.handle_retrieve(payload)
        elif path == "/generate":
            self.handle_generate(payload)
        elif path == "/evaluate":
            self.handle_evaluate(payload)
        else:
            self.send_error(404)

    # ── /run ─────────────────────────────────────────────────────────────

    def handle_run(self, payload: dict) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        state: EPICDemoState = self.server.state

        def write_event(event: dict) -> None:
            self.write_chunk(json.dumps(event).encode("utf-8") + b"\n")

        def emit(name: str, **kw: Any) -> None:
            write_event({"event": name, **kw})

        try:
            args = argparse.Namespace(
                embedding_model=CONTRIEVER_MODEL,
                llm_model=state.llm_model,
                llm_timeout=state.llm_timeout,
                llm_server_url=state.llm_server_url,
                events=False,
                event_sink=write_event,
            )
            result = run_pipeline(payload, args, encoder=state.encoder)

            # ── Build EPIC index from fine evaluations ────────────────
            chunks_by_index = {int(c["index"]): c for c in payload["chunks"]}
            preferences_raw = [p["preference"] for p in payload.get("preferences", [])]

            epic_entries: list[dict[str, Any]] = []
            for evaluation in result["fine_evaluations"]:
                chunk = chunks_by_index.get(int(evaluation["chunk_index"]), {})
                for entry in evaluation["kept_entries"]:
                    epic_entries.append({
                        "chunk_text": chunk.get("text", ""),
                        "article_title": chunk.get("article_title", ""),
                        "instruction": entry["instruction"],
                        "preference": entry["preference"],
                    })

            epic_index: faiss.IndexFlatIP | None = None
            epic_index_bytes = 0
            if epic_entries:
                instr_texts = [e["instruction"] for e in epic_entries]
                instr_vecs = state.encoder.encode(instr_texts)
                epic_index = faiss.IndexFlatIP(state.encoder.dimension)
                epic_index.add(instr_vecs)
                epic_index_bytes = len(faiss.serialize_index(epic_index))

            # ── Build RAG index from all chunks ───────────────────────
            all_chunks = payload["chunks"]
            rag_chunks = [
                {"chunk_text": c["text"], "article_title": c.get("article_title", "")}
                for c in all_chunks
            ]
            chunk_vecs = state.encoder.encode([c["text"] for c in all_chunks])
            rag_index = faiss.IndexFlatIP(state.encoder.dimension)
            rag_index_bytes = 0
            if chunk_vecs.shape[0]:
                rag_index.add(chunk_vecs)
                rag_index_bytes = len(faiss.serialize_index(rag_index))

            # ── Store session ─────────────────────────────────────────
            import uuid as _uuid
            session = DemoSession()
            session.session_id = str(_uuid.uuid4())
            session.epic_index = epic_index
            session.epic_entries = epic_entries
            session.epic_index_bytes = epic_index_bytes
            session.rag_index = rag_index
            session.rag_chunks = rag_chunks
            session.rag_index_bytes = rag_index_bytes
            session.preferences = preferences_raw
            session.preference_vectors = (
                state.encoder.encode(preferences_raw) if preferences_raw else None
            )
            state.session = session

            write_event({
                "event": "complete",
                "result": result,
                "session_id": session.session_id,
                "epic_entries": len(epic_entries),
                "rag_chunks": len(rag_chunks),
            })

        except Exception as e:
            write_event({"event": "error", "error": str(e), "error_type": e.__class__.__name__})
        finally:
            self.write_chunk(b"", final=True)

    # ── /generate ────────────────────────────────────────────────────────

    def handle_generate(self, payload: dict) -> None:
        state: EPICDemoState = self.server.state
        session = state.session

        if session is None:
            self.write_json({"error": "No indexed session. Run /run first."}, 400)
            return

        question: str = payload.get("question", "")
        top_k: int = int(payload.get("top_k", 5))

        if not question:
            self.write_json({"error": "Missing 'question'"}, 400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        write_lock = threading.Lock()

        def write_event(event: dict) -> None:
            line = json.dumps(event).encode("utf-8") + b"\n"
            with write_lock:
                self.write_chunk(line)

        def emit(name: str, **kw: Any) -> None:
            write_event({"event": name, **kw})

        try:
            # ── Retrieve (timed) ──────────────────────────────────────
            t0 = time.time()
            epic_docs = epic_retrieve(state, session, question, top_k)
            epic_retr_ms = (time.time() - t0) * 1000

            t0 = time.time()
            rag_docs = rag_retrieve(state, session, question, top_k)
            rag_retr_ms = (time.time() - t0) * 1000

            emit("retrieved",
                 epic_docs=epic_docs, rag_docs=rag_docs,
                 epic_retr_ms=round(epic_retr_ms, 1),
                 rag_retr_ms=round(rag_retr_ms, 1),
                 epic_index_bytes=session.epic_index_bytes,
                 rag_index_bytes=session.rag_index_bytes,
                 epic_entries=len(session.epic_entries),
                 rag_chunks=len(session.rag_chunks))

            # ── Parallel generation ───────────────────────────────────
            epic_context = build_epic_context(epic_docs)
            epic_user = f"Retrieved documents:\n{epic_context}\n\nQuestion: {question}"

            rag_context = build_rag_context(rag_docs)
            rag_user = f"Retrieved documents:\n{rag_context}\n\nQuestion: {question}"

            epic_response_holder: list[str] = []
            rag_response_holder: list[str] = []

            emit("epic_start")
            emit("rag_start")

            def gen_epic() -> None:
                text = _gen_streaming(state, EPIC_GEN_SYSTEM, epic_user, "epic", emit)
                epic_response_holder.append(text)
                emit("epic_done", text=text)

            def gen_rag() -> None:
                text = _gen_streaming(state, RAG_GEN_SYSTEM, rag_user, "rag", emit)
                rag_response_holder.append(text)
                emit("rag_done", text=text)

            with ThreadPoolExecutor(max_workers=2) as ex:
                ef = ex.submit(gen_epic)
                rf = ex.submit(gen_rag)
                ef.result()
                rf.result()

            epic_response = epic_response_holder[0] if epic_response_holder else ""
            rag_response = rag_response_holder[0] if rag_response_holder else ""
            top_pref = session.preferences[0] if session.preferences else ""

            emit("complete",
                 epic_response=epic_response, rag_response=rag_response,
                 top_preference=top_pref,
                 epic_docs=epic_docs, rag_docs=rag_docs,
                 epic_retr_ms=round(epic_retr_ms, 1),
                 rag_retr_ms=round(rag_retr_ms, 1),
                 epic_index_bytes=session.epic_index_bytes,
                 rag_index_bytes=session.rag_index_bytes)

        except Exception as e:
            write_event({"event": "error", "error": str(e), "error_type": e.__class__.__name__})
        finally:
            with write_lock:
                self.write_chunk(b"", final=True)

    # ── /evaluate ────────────────────────────────────────────────────────

    # ── /load_persona ─────────────────────────────────────────────────────
    def handle_load_persona(self, payload: dict) -> None:
        """Load a pre-built persona index from disk (built by preindex_corpus.py)."""
        state: EPICDemoState = self.server.state

        if not state.preindex_dir:
            self.write_json({"error": "Server was not started with --preindex-dir."}, 400)
            return

        persona_index = payload.get("persona_index")
        if persona_index is None:
            self.write_json({"error": "Missing 'persona_index'."}, 400)
            return
        persona_index = int(persona_index)

        try:
            session = load_persona_session(state, persona_index)
        except FileNotFoundError as e:
            self.write_json({"error": str(e)}, 404)
            return
        except Exception as e:
            self.write_json({"error": f"Failed to load persona index: {e}"}, 500)
            return

        with state._lock:
            state._session = session

        self.write_json({
            "ok": True,
            "persona_index": persona_index,
            "session_id": session.session_id,
            "epic_entries": len(session.epic_entries),
            "rag_chunks": len(session.rag_chunks),
            "epic_index_bytes": session.epic_index_bytes,
            "rag_index_bytes": session.rag_index_bytes,
        })

    # ── /curated_questions ──────────────────────────────────────────────
    def handle_curated_questions(self, payload: dict) -> None:
        """Return pre-computed (generated + evaluated) Q&A for a persona —
        built offline by curate_qa.py. Instant, no LLM calls."""
        state: EPICDemoState = self.server.state

        if not state.preindex_dir:
            self.write_json({"error": "Server was not started with --preindex-dir."}, 400)
            return

        persona_index = payload.get("persona_index")
        if persona_index is None:
            self.write_json({"error": "Missing 'persona_index'."}, 400)
            return
        persona_index = int(persona_index)

        curated_path = os.path.join(state.preindex_dir, f"persona_{persona_index}", "curated_qa.json")
        if not os.path.exists(curated_path):
            self.write_json({"error": f"No curated Q&A for persona {persona_index}. Run curate_qa.py first."}, 404)
            return

        with open(curated_path) as f:
            curated = json.load(f)
        self.write_json({"persona_index": persona_index, "questions": curated})

    # ── /retrieve (retrieval-only, no generation) ───────────────────────────
    def handle_retrieve(self, payload: dict) -> None:
        """Run retrieval only — for the Retrieval demo screen. Fast, non-streaming."""
        state: EPICDemoState = self.server.state
        session = state.session

        if session is None:
            self.write_json({"error": "No indexed session. Load a persona or run /run first."}, 400)
            return

        question: str = payload.get("question", "")
        top_k: int = int(payload.get("top_k", 5))
        if not question:
            self.write_json({"error": "Missing 'question'"}, 400)
            return

        # Step 1: query embedding — shared by both systems (one Contriever forward pass)
        t0 = time.time()
        q_vec = state.encoder.encode([question])
        embed_ms = (time.time() - t0) * 1000

        # Step 2: EPIC query steering — match the query against the persona's
        # preference embeddings, fold the top-1 preference into the query
        # vector. This is EPIC-only; Plain RAG searches the raw query vector.
        t0 = time.time()
        steered_vec, matched_pref, steer_score = epic_steer_query(session, q_vec)
        steer_ms = (time.time() - t0) * 1000

        # Step 3a: EPIC — search the (small) instruction index with the steered vector
        t0 = time.time()
        epic_docs = epic_search(session, steered_vec, top_k)
        epic_search_ms = (time.time() - t0) * 1000

        # Step 3b: RAG — search the (large) raw chunk index with the raw query vector
        t0 = time.time()
        rag_docs = rag_search(session, q_vec, top_k)
        rag_search_ms = (time.time() - t0) * 1000

        self.write_json({
            "epic_docs": epic_docs,
            "rag_docs": rag_docs,
            # Breakdown: embedding is shared; steering is EPIC-only; search is per-system
            "embed_ms": round(embed_ms, 1),
            "steer_ms": round(steer_ms, 1),
            "matched_preference": matched_pref,
            "steer_score": round(steer_score, 3),
            "epic_search_ms": round(epic_search_ms, 1),
            "rag_search_ms": round(rag_search_ms, 1),
            # Totals — kept for backward compatibility
            "epic_retr_ms": round(embed_ms + steer_ms + epic_search_ms, 1),
            "rag_retr_ms": round(embed_ms + rag_search_ms, 1),
            "epic_index_bytes": session.epic_index_bytes,
            "rag_index_bytes": session.rag_index_bytes,
            "epic_entries": len(session.epic_entries),
            "rag_chunks": len(session.rag_chunks),
        })

    def handle_evaluate(self, payload: dict) -> None:
        state: EPICDemoState = self.server.state
        question: str = payload.get("question", "")
        preference: str = payload.get("preference", "")
        epic_response: str = payload.get("epic_response", "")
        rag_response: str = payload.get("rag_response", "")

        if not all([question, preference, epic_response, rag_response]):
            self.write_json({"error": "Missing required fields: question, preference, epic_response, rag_response"}, 400)
            return

        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                epic_fut = ex.submit(evaluate_single, state, question, preference, epic_response)
                rag_fut = ex.submit(evaluate_single, state, question, preference, rag_response)
                epic_eval = epic_fut.result()
                rag_eval = rag_fut.result()

            self.write_json({"epic": epic_eval, "rag": rag_eval})

        except Exception as e:
            self.write_json({"error": str(e), "error_type": e.__class__.__name__}, 500)

    # ── helpers ──────────────────────────────────────────────────────────

    def write_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def write_chunk(self, data: bytes, final: bool = False) -> None:
        if final:
            self.wfile.write(b"0\r\n\r\n")
        else:
            self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
            self.wfile.write(data)
            self.wfile.write(b"\r\n")
        self.wfile.flush()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))


# ── main ──────────────────────────────────────────────────────────────────

def wait_for_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if 200 <= r.status < 500:
                    return
        except Exception as e:
            last_err = e
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {url}: {last_err}")


# Default generation LLM (Llama 70B) — set to same as indexing if not available
DEMO_GEN_VLLM_MODEL = "meta-llama/Llama-3.1-70B-Instruct"
DEMO_GEN_VLLM_URL = "http://127.0.0.1:8009"


def main() -> int:
    parser = argparse.ArgumentParser(description="EPIC Demo Server with /run, /generate, /evaluate.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    # Indexing LLM (Qwen3-8B for fine verification)
    parser.add_argument("--llm-model", default=DEMO_VLLM_MODEL)
    parser.add_argument("--llm-server-url", default=DEMO_VLLM_URL)
    parser.add_argument("--llm-timeout", type=int, default=180)
    # Generation LLM (Llama 70B for response generation) — falls back to indexing LLM
    parser.add_argument("--eval-llm-model", default="", help="Evaluation LLM (Llama 70B). Falls back to indexing LLM.")
    parser.add_argument("--eval-llm-server-url", default="")
    parser.add_argument("--preindex-dir", default="", help="Directory of pre-built persona indexes from preindex_corpus.py")
    args = parser.parse_args()

    print("Loading Contriever...", flush=True)
    encoder = ContrieverEncoder(CONTRIEVER_MODEL)
    encoder.encode(["warmup"])
    print(f"Contriever ready (dim={encoder.dimension})", flush=True)

    print(f"Waiting for indexing vLLM at {args.llm_server_url}...", flush=True)
    wait_for_http(f"{args.llm_server_url}/health")
    print(f"Indexing LLM ({args.llm_model}) ready.", flush=True)

    eval_url = args.eval_llm_server_url or args.llm_server_url
    eval_model = args.eval_llm_model or args.llm_model
    if args.eval_llm_server_url and args.eval_llm_server_url != args.llm_server_url:
        print(f"Waiting for evaluation vLLM at {eval_url}...", flush=True)
        wait_for_http(f"{eval_url}/health")
    print(f"Evaluation LLM ({eval_model}) ready.", flush=True)

    state = EPICDemoState(
        encoder=encoder,
        llm_model=args.llm_model,
        llm_server_url=args.llm_server_url,
        llm_timeout=args.llm_timeout,
        eval_llm_model=eval_model,
        eval_llm_server_url=eval_url,
        preindex_dir=args.preindex_dir,
    )

    server = EPICDemoHTTPServer((args.host, args.port), EPICDemoHandler, state)
    print(f"EPIC Demo Server ready at http://{args.host}:{args.port}", flush=True)
    print(f"  Indexing LLM : {args.llm_model} @ {args.llm_server_url}", flush=True)
    print(f"  Evaluation LLM : {eval_model} @ {eval_url}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
