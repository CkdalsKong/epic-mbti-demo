#!/usr/bin/env python3
"""
Pre-index the full corpus for all 57 PrefWiki personas.

Run once on H200 before the demo:

  python preindex_corpus.py \
    --corpus   /path/to/corpus.jsonl \
    --prefwiki /path/to/PrefWiki.json \
    --out-dir  ./preindex \
    --llm-server-url http://127.0.0.1:8008 \
    --personas 0-56          # or specific: 0,3,7

Each row in corpus.jsonl must have at least:
  {"text": "...", "title": "..."}      (title optional, falls back to "")

Output layout:
  preindex/
    persona_0/
      epic_index.faiss
      epic_entries.json      # [{chunk_text, article_title, instruction, preference, score}]
      rag_index.faiss
      rag_chunks.json        # [{chunk_text, article_title}]
      meta.json              # {persona_index, epic_entries, rag_chunks, epic_index_bytes, rag_index_bytes}
    persona_1/ ...
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from tqdm import tqdm

import faiss
import numpy as np

# Reuse the runtime already in this directory
sys.path.insert(0, os.path.dirname(__file__))
from epic_runtime import ContrieverEncoder, CONTRIEVER_MODEL
import urllib.request

# ── Helpers ────────────────────────────────────────────────────────────────

def load_corpus(path: str) -> list[dict]:
    """Load a JSONL corpus.

    Supports two formats:
      - PrefWiki-style:   {"text": "...", "title": "..."}
      - MBTI-demo-style:  {"text": "...", "source": "...", "topic": "...", "raw_text": "..."}
        where `text` is the contextual chunk (used for embedding) and
        `raw_text` is the original text shown to the LLM.
    """
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            # Prefer raw_text for LLM display, fall back to text
            display_text = obj.get("raw_text") or obj["text"]
            embed_text = obj["text"]   # contextual chunk for embedding
            # Build a human-readable title
            title = (
                obj.get("title")
                or obj.get("article_title")
                or f"{obj.get('source', '')} — {obj.get('topic', '')}".strip(" —")
                or ""
            )
            chunks.append({
                "index": i,
                "text": embed_text,        # used for Contriever embedding + LLM context
                "display_text": display_text,
                "article_title": title,
            })
    return chunks


def load_prefwiki(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chat_completion(llm_url: str, model: str, messages: list[dict], timeout: int = 120) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": 256,
        "temperature": 0.0,
        # Qwen3 specific: disable thinking to get direct answers
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{llm_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    content = data["choices"][0]["message"]["content"].strip()
    # Strip <think>...</think> blocks in case thinking mode is still active
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content


FINE_SYSTEM = (
    "You are a strict preference alignment filter. "
    "Respond with EXACTLY one line — no preamble, no explanation:\n"
    "  KEEP: <one concise instruction on how to use this chunk>\n"
    "  DISCARD\n"
    "Output nothing else."
)


def fine_verify_chunk(
    chunk: dict,
    preferences: list[str],
    llm_url: str,
    model: str,
    timeout: int,
) -> dict | None:
    pref_text = "\n".join(f"- {p}" for p in preferences)
    user_msg = (
        f"Preferences:\n{pref_text}\n\n"
        f"Chunk:\n{chunk['text'][:800]}\n\n"
        "KEEP or DISCARD?"
    )
    try:
        reply = chat_completion(llm_url, model, [
            {"role": "system", "content": FINE_SYSTEM},
            {"role": "user", "content": user_msg},
        ], timeout=timeout)
    except Exception as e:
        print(f"\n  LLM error chunk {chunk['index']}: {e}", flush=True)
        return None

    # Match KEEP anywhere in the reply (handles stray preamble)
    m = re.search(r"KEEP\s*:\s*(.+)", reply, re.IGNORECASE)
    if m:
        instruction = m.group(1).strip() or "Use this chunk for preference-aligned answers."
        return {"instruction": instruction}
    return None


def build_faiss_flat(vectors: np.ndarray) -> faiss.IndexFlatIP:
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    if vectors.shape[0] > 0:
        index.add(vectors)
    return index


def parse_persona_range(spec: str, total: int) -> list[int]:
    """Parse '0-56', '0,3,7', or '5' into a list of indices."""
    indices = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a), int(b) + 1))
        else:
            indices.add(int(part))
    return sorted(i for i in indices if 0 <= i < total)


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-index PrefWiki personas against a corpus.")
    parser.add_argument("--corpus",   required=True, help="Path to corpus JSONL (one chunk per line, needs 'text' field)")
    parser.add_argument("--prefwiki", required=True, help="Path to PrefWiki.json")
    parser.add_argument("--out-dir",  default="./preindex", help="Output directory for indexes")
    parser.add_argument("--personas", default="0-56", help="Personas to index, e.g. '0-56' or '0,3,7'")
    parser.add_argument("--llm-model",      default="Qwen/Qwen3-8B")
    parser.add_argument("--llm-server-url", default="http://127.0.0.1:8008")
    parser.add_argument("--llm-timeout",    type=int, default=120)
    parser.add_argument("--coarse-threshold", type=float, default=0.35,
                        help="Cosine sim threshold for coarse filter (higher = fewer candidates for LLM)")
    parser.add_argument("--top-prefs",  type=int, default=10, help="How many preference blocks to use per persona")
    parser.add_argument("--workers",    type=int, default=32, help="Parallel LLM workers for fine verification")
    parser.add_argument("--resume",     action="store_true", help="Skip personas that already have meta.json")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("Loading corpus...", flush=True)
    t0 = time.time()
    chunks = load_corpus(args.corpus)
    print(f"  {len(chunks)} chunks loaded in {time.time()-t0:.1f}s", flush=True)

    print("Loading PrefWiki...", flush=True)
    personas = load_prefwiki(args.prefwiki)
    print(f"  {len(personas)} personas", flush=True)

    persona_indices = parse_persona_range(args.personas, len(personas))
    print(f"Will index personas: {persona_indices}", flush=True)

    print("Loading Contriever...", flush=True)
    encoder = ContrieverEncoder(CONTRIEVER_MODEL)
    encoder.encode(["warmup"])
    print(f"  Contriever ready (dim={encoder.dimension})", flush=True)

    print("Encoding all corpus chunks...", flush=True)
    t0 = time.time()
    chunk_texts = [c["text"] for c in chunks]
    with tqdm(total=len(chunks), desc="  embedding corpus", unit="chunk", dynamic_ncols=True) as pbar:
        chunk_vectors = encoder.encode(
            chunk_texts,
            on_batch=lambda done, total: pbar.update(done - pbar.n),
        )
    print(f"  Encoded {len(chunks)} chunks in {time.time()-t0:.1f}s", flush=True)

    # Build the shared RAG index (same for all personas)
    rag_index = build_faiss_flat(chunk_vectors)
    rag_index_bytes = len(faiss.serialize_index(rag_index))
    rag_chunks = [{"chunk_text": c.get("display_text", c["text"]), "article_title": c["article_title"]} for c in chunks]
    print(f"  RAG index: {rag_index_bytes/1e6:.1f} MB, {len(rag_chunks)} chunks", flush=True)

    for pi in persona_indices:
        persona_data = personas[pi]
        out_dir = os.path.join(args.out_dir, f"persona_{pi}")
        meta_path = os.path.join(out_dir, "meta.json")

        if args.resume and os.path.exists(meta_path):
            print(f"\n[{pi}] Skipping (already indexed)", flush=True)
            continue

        os.makedirs(out_dir, exist_ok=True)

        pref_blocks = persona_data["preference_blocks"][: args.top_prefs]
        preferences = [b["preference"] for b in pref_blocks]
        print(f"\n[{pi}] {len(preferences)} preferences | {len(chunks)} chunks", flush=True)

        # Encode preferences
        pref_vectors = encoder.encode(preferences)  # (P, D)

        # ── Coarse filter ──────────────────────────────────────────────────
        print(f"  Coarse filter (threshold={args.coarse_threshold})...", flush=True)
        # cosine similarity: chunk_vectors @ pref_vectors.T → (N, P)
        sim = chunk_vectors @ pref_vectors.T  # already L2-normalized by ContrieverEncoder
        max_scores = sim.max(axis=1)          # (N,)
        best_pref_idx = sim.argmax(axis=1)    # (N,)
        coarse_mask = max_scores >= args.coarse_threshold
        coarse_indices = np.where(coarse_mask)[0]
        print(f"  Coarse kept: {len(coarse_indices)}/{len(chunks)}", flush=True)

        # ── Fine LLM verification (parallel) ──────────────────────────────
        print(f"  Fine verification via LLM ({args.llm_model}), workers={args.workers}...", flush=True)
        epic_entries = []

        def verify_one(ci: int):
            chunk = chunks[ci]
            result = fine_verify_chunk(chunk, preferences, args.llm_server_url, args.llm_model, args.llm_timeout)
            return ci, result

        with tqdm(total=len(coarse_indices), desc=f"  p{pi} fine-verify", unit="chunk", dynamic_ncols=True) as pbar:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = {ex.submit(verify_one, int(ci)): int(ci) for ci in coarse_indices}
                for fut in as_completed(futures):
                    ci, result = fut.result()
                    if result:
                        best_pref = preferences[best_pref_idx[ci]]
                        chunk = chunks[ci]
                        epic_entries.append({
                            "chunk_text": chunk.get("display_text", chunk["text"]),
                            "article_title": chunk["article_title"],
                            "instruction": result["instruction"],
                            "preference": best_pref,
                            "score": float(max_scores[ci]),
                        })
                    pbar.set_postfix(kept=len(epic_entries))
                    pbar.update(1)

        print(f"  EPIC entries: {len(epic_entries)}", flush=True)

        # ── Build EPIC FAISS index ─────────────────────────────────────────
        epic_index_bytes = 0
        if epic_entries:
            instr_texts = [e["instruction"] for e in epic_entries]
            instr_vecs = encoder.encode(instr_texts)
            epic_index = build_faiss_flat(instr_vecs)
            epic_index_bytes = len(faiss.serialize_index(epic_index))
            faiss.write_index(epic_index, os.path.join(out_dir, "epic_index.faiss"))
            print(f"  EPIC index: {epic_index_bytes/1e6:.1f} MB", flush=True)
        else:
            # Write empty index
            empty = faiss.IndexFlatIP(encoder.dimension)
            faiss.write_index(empty, os.path.join(out_dir, "epic_index.faiss"))

        with open(os.path.join(out_dir, "epic_entries.json"), "w") as f:
            json.dump(epic_entries, f, ensure_ascii=False)

        # Save per-persona RAG index (same structure, different file)
        faiss.write_index(rag_index, os.path.join(out_dir, "rag_index.faiss"))
        with open(os.path.join(out_dir, "rag_chunks.json"), "w") as f:
            json.dump(rag_chunks, f, ensure_ascii=False)

        meta = {
            "persona_index": pi,
            "preferences": preferences,
            "epic_entries": len(epic_entries),
            "rag_chunks": len(rag_chunks),
            "epic_index_bytes": epic_index_bytes,
            "rag_index_bytes": rag_index_bytes,
            "coarse_threshold": args.coarse_threshold,
            "corpus_size": len(chunks),
        }
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        print(f"  Saved to {out_dir}", flush=True)

    print("\nAll done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
