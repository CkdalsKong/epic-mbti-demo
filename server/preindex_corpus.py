#!/usr/bin/env python3
"""
Pre-index the full corpus for all 57 PrefWiki personas.

This faithfully replicates the real EPIC indexing pipeline (EPIC_indexing.py
+ EPIC_utils.py), not a simplified approximation:

  1. Coarse cosine filter — a chunk is kept if it exceeds --coarse-threshold
     against ANY persona preference. Unlike a naive "best match" filter, we
     track *every* preference that matched (not just the top-1), because
     step 2 only shows the LLM the preferences that already passed here.
  2. Fine LLM filtering — uses the actual filtering_systemprompt.txt /
     filtering_userprompt.txt (XML decision/reason/relevant_preferences),
     shown only the chunk's coarse-matched preferences (shuffled, seeded by
     chunk index, exactly like EPIC_utils.process_chunk_rand_prefs).
  3. Instruction generation — a SEPARATE LLM call using
     instruction_systemprompt.txt / instruction_userprompt.txt, fed the
     filtering step's <reason> plus the matched preferences. This is what
     actually gets embedded into the EPIC FAISS index — not the filtering
     decision, not the raw chunk.

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
    chunk_vectors.npy        # shared corpus embeddings (cached across personas)
    rag_index.faiss          # shared RAG (raw chunk) FAISS index
    rag_chunks.json          # shared RAG chunk metadata
    persona_0/
      epic_index.faiss       # this persona's EPIC instruction index
      epic_entries.json      # [{chunk_text, article_title, instruction, preference, reason, score}]
      meta.json              # {persona_index, epic_entries, rag_chunks, epic_index_bytes, rag_index_bytes, rag_index_path}
    persona_1/ ...
"""

import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from bs4 import BeautifulSoup
from tqdm import tqdm

import faiss
import numpy as np

# Reuse the runtime already in this directory
sys.path.insert(0, os.path.dirname(__file__))
from epic_runtime import ContrieverEncoder, CONTRIEVER_MODEL
import urllib.request

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


FILTERING_SYSTEM = load_prompt("filtering_systemprompt.txt")
FILTERING_USER = load_prompt("filtering_userprompt.txt")
INSTRUCTION_SYSTEM = load_prompt("instruction_systemprompt.txt")
INSTRUCTION_USER = load_prompt("instruction_userprompt.txt")


def fill_template(template: str, **kwargs: str) -> str:
    """Same as EPIC_utils.format_prompt — plain string replace, not
    str.format(), so curly braces inside chunk text don't break it."""
    out = template
    for key, value in kwargs.items():
        out = out.replace("{" + key + "}", value)
    return out


# ── XML response parsing (matches EPIC_utils.py exactly) ───────────────────

def clean_preference_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if text.replace(",", "").replace(" ", "").isdigit():
        return text
    text = re.sub(r"^Preference\s+\d+:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d+\.\s*", "", text)
    text = text.strip("\"'")
    return text.strip()


def parse_decision_and_reason_preferences(text: str) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(text, "html.parser")
    decision_tag = soup.find("decision")
    reason_tag = soup.find("reason")
    preference_tags = soup.find_all("preference")
    decision = decision_tag.text.strip() if decision_tag else ""
    reason = reason_tag.text.strip() if reason_tag else ""
    preferences = [t.text.strip() for t in preference_tags if t.text.strip()]
    preferences = [clean_preference_text(p) for p in preferences]
    return decision, reason, preferences


def map_preference_numbers_to_text(pref_text: str, preference_list: list[str]) -> str:
    """If the LLM answered with a number (e.g. '2') instead of the literal
    preference text, map it back using the SAME (shuffled) list that was
    shown to it in the prompt."""
    if not pref_text or not preference_list:
        return pref_text
    numbers = re.findall(r"\d+", pref_text)
    if not numbers:
        return pref_text
    mapped = []
    for num in numbers:
        idx = int(num) - 1
        mapped.append(preference_list[idx] if 0 <= idx < len(preference_list) else num)
    return "; ".join(mapped) if mapped else pref_text


def parse_instruction(text: str) -> str | None:
    soup = BeautifulSoup(text, "html.parser")
    tag = soup.find("instruction")
    if tag:
        return tag.text.strip()
    return text.strip() if text else None


# ── Corpus / persona loading ─────────────────────────────────────────────

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
            display_text = obj.get("raw_text") or obj["text"]
            embed_text = obj["text"]
            title = (
                obj.get("title")
                or obj.get("article_title")
                or f"{obj.get('source', '')} — {obj.get('topic', '')}".strip(" —")
                or ""
            )
            chunks.append({
                "index": i,
                "text": embed_text,
                "display_text": display_text,
                "article_title": title,
            })
    return chunks


def load_prefwiki(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chat_completion(llm_url: str, model: str, messages: list[dict], max_tokens: int = 512, timeout: int = 120) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
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
    # Strip <think>...</think> blocks in case a reasoning model leaks them
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    return content


# ── Step 2: fine LLM filtering (real filtering prompt) ──────────────────────

def fine_filter_chunk(
    chunk_idx: int,
    chunk_text: str,
    relevant_prefs: list[str],
    llm_url: str,
    model: str,
    timeout: int,
) -> dict | None:
    """Returns {"reason": str, "relevant_preferences": [str]} if Keep, else None."""
    shuffled = relevant_prefs[:]
    random.Random(chunk_idx).shuffle(shuffled)
    preference_text = "\n".join(f"{i+1}. '{p}'" for i, p in enumerate(shuffled))
    user_prompt = fill_template(FILTERING_USER, preference=preference_text, chunk=chunk_text)

    try:
        reply = chat_completion(
            llm_url, model,
            [{"role": "system", "content": FILTERING_SYSTEM}, {"role": "user", "content": user_prompt}],
            max_tokens=512, timeout=timeout,
        )
    except Exception as e:
        print(f"\n  [filter] LLM error chunk {chunk_idx}: {e}", flush=True)
        return None

    decision, reason, preferences = parse_decision_and_reason_preferences(reply)
    preferences = [map_preference_numbers_to_text(p, shuffled) for p in preferences]

    if decision.strip().lower() != "keep":
        return None
    if not preferences:
        preferences = shuffled[:1]  # fallback: keep at least the top coarse match
    return {"reason": reason, "relevant_preferences": preferences}


# ── Step 3: instruction generation (real instruction prompt) ───────────────

def generate_instruction(
    chunk_text: str,
    relevant_preferences: list[str],
    reason: str,
    llm_url: str,
    model: str,
    timeout: int,
) -> str | None:
    preference_text = "\n".join(f"- {p}" for p in relevant_preferences)
    user_prompt = fill_template(INSTRUCTION_USER, preference=preference_text, chunk=chunk_text, reason=reason)

    try:
        reply = chat_completion(
            llm_url, model,
            [{"role": "system", "content": INSTRUCTION_SYSTEM}, {"role": "user", "content": user_prompt}],
            max_tokens=256, timeout=timeout,
        )
    except Exception as e:
        print(f"\n  [instruction] LLM error: {e}", flush=True)
        return None
    return parse_instruction(reply)


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
    parser.add_argument("--llm-model",      default="meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--llm-server-url", default="http://127.0.0.1:8008")
    parser.add_argument("--llm-timeout",    type=int, default=120)
    parser.add_argument("--coarse-threshold", type=float, default=0.35,
                        help="Cosine sim threshold for coarse filter (higher = fewer candidates for LLM)")
    parser.add_argument("--top-prefs",  type=int, default=10, help="How many preference blocks to use per persona")
    parser.add_argument("--workers",    type=int, default=32, help="Parallel LLM workers for fine filtering")
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

    # ── Embeddings: load cache or encode ──────────────────────────────────
    cache_vec = os.path.join(args.out_dir, "chunk_vectors.npy")
    cache_rag  = os.path.join(args.out_dir, "rag_index.faiss")
    cache_meta = os.path.join(args.out_dir, "rag_chunks.json")

    if os.path.exists(cache_vec) and os.path.exists(cache_rag) and os.path.exists(cache_meta):
        print(f"Loading cached embeddings from {cache_vec} ...", flush=True)
        chunk_vectors = np.load(cache_vec)
        rag_index = faiss.read_index(cache_rag)
        with open(cache_meta) as f:
            rag_chunks = json.load(f)
        rag_index_bytes = len(faiss.serialize_index(rag_index))
        print(f"  Loaded {len(chunk_vectors)} vectors, RAG index {rag_index_bytes/1e6:.1f} MB", flush=True)
        print("Loading Contriever (for preference/instruction embedding)...", flush=True)
        encoder = ContrieverEncoder(CONTRIEVER_MODEL)
        encoder.encode(["warmup"])
        print(f"  Contriever ready (dim={encoder.dimension})", flush=True)
    else:
        print("Loading Contriever...", flush=True)
        encoder = ContrieverEncoder(CONTRIEVER_MODEL)
        encoder.encode(["warmup"])
        print(f"  Contriever ready (dim={encoder.dimension})", flush=True)

        print(f"Encoding {len(chunks)} corpus chunks (will cache to {cache_vec})...", flush=True)
        t0 = time.time()
        chunk_texts = [c["text"] for c in chunks]
        with tqdm(total=len(chunks), desc="  embedding corpus", unit="chunk", dynamic_ncols=True) as pbar:
            chunk_vectors = encoder.encode(
                chunk_texts,
                on_batch=lambda done, total: pbar.update(done - pbar.n),
            )
        print(f"  Encoded in {time.time()-t0:.1f}s — saving cache...", flush=True)
        np.save(cache_vec, chunk_vectors)
        print(f"  Saved {cache_vec}", flush=True)

        rag_index = build_faiss_flat(chunk_vectors)
        rag_index_bytes = len(faiss.serialize_index(rag_index))
        rag_chunks = [{"chunk_text": c.get("display_text", c["text"]), "article_title": c["article_title"]} for c in chunks]
        faiss.write_index(rag_index, cache_rag)
        with open(cache_meta, "w") as f:
            json.dump(rag_chunks, f, ensure_ascii=False)
        print(f"  RAG index: {rag_index_bytes/1e6:.1f} MB, {len(rag_chunks)} chunks — cached", flush=True)

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

        pref_vectors = encoder.encode(preferences)  # (P, D)

        # ── Step 1: coarse cosine filter — track EVERY matching preference ──
        print(f"  Coarse filter (threshold={args.coarse_threshold})...", flush=True)
        sim = chunk_vectors @ pref_vectors.T            # (N, P), already L2-normalized
        above = sim >= args.coarse_threshold            # (N, P) boolean
        coarse_mask = above.any(axis=1)
        coarse_indices = np.where(coarse_mask)[0]
        print(f"  Coarse kept: {len(coarse_indices)}/{len(chunks)}", flush=True)

        # ── Step 2 + 3: fine LLM filter, then instruction generation ───────
        print(f"  Fine filtering + instruction generation via LLM ({args.llm_model}), workers={args.workers}...", flush=True)
        epic_entries = []

        def process_one(ci: int):
            chunk = chunks[ci]
            matched_idx = np.where(above[ci])[0]
            relevant_prefs = [preferences[k] for k in matched_idx]
            best_score = float(sim[ci, matched_idx].max())
            chunk_text = chunk.get("display_text", chunk["text"])

            filt = fine_filter_chunk(ci, chunk_text, relevant_prefs, args.llm_server_url, args.llm_model, args.llm_timeout)
            if filt is None:
                return None

            instruction = generate_instruction(
                chunk_text, filt["relevant_preferences"], filt["reason"],
                args.llm_server_url, args.llm_model, args.llm_timeout,
            )
            if not instruction:
                return None

            return {
                "chunk_text": chunk_text,
                "article_title": chunk["article_title"],
                "instruction": instruction,
                "preference": "; ".join(filt["relevant_preferences"]),
                "reason": filt["reason"],
                "score": best_score,
            }

        with tqdm(total=len(coarse_indices), desc=f"  p{pi} filter+instruct", unit="chunk", dynamic_ncols=True) as pbar:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = {ex.submit(process_one, int(ci)): int(ci) for ci in coarse_indices}
                for fut in as_completed(futures):
                    entry = fut.result()
                    if entry:
                        epic_entries.append(entry)
                    pbar.set_postfix(kept=len(epic_entries))
                    pbar.update(1)

        print(f"  EPIC entries: {len(epic_entries)}", flush=True)

        # ── Build EPIC FAISS index over the generated INSTRUCTIONS ─────────
        epic_index_bytes = 0
        if epic_entries:
            instr_texts = [e["instruction"] for e in epic_entries]
            instr_vecs = encoder.encode(instr_texts)
            epic_index = build_faiss_flat(instr_vecs)
            epic_index_bytes = len(faiss.serialize_index(epic_index))
            faiss.write_index(epic_index, os.path.join(out_dir, "epic_index.faiss"))
            print(f"  EPIC index: {epic_index_bytes/1e6:.1f} MB", flush=True)
        else:
            empty = faiss.IndexFlatIP(encoder.dimension)
            faiss.write_index(empty, os.path.join(out_dir, "epic_index.faiss"))

        with open(os.path.join(out_dir, "epic_entries.json"), "w") as f:
            json.dump(epic_entries, f, ensure_ascii=False)

        # RAG index is shared — store absolute path in meta instead of copying 2.3GB per persona
        meta = {
            "persona_index": pi,
            "preferences": preferences,
            "epic_entries": len(epic_entries),
            "rag_chunks": len(rag_chunks),
            "epic_index_bytes": epic_index_bytes,
            "rag_index_bytes": rag_index_bytes,
            "rag_index_path": os.path.abspath(cache_rag),
            "rag_chunks_path": os.path.abspath(cache_meta),
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
