"""
EPIC indexing pipeline for MBTI demo.
Per MBTI type:
  1. Load chunks + preferences
  2. Cosine filter (preference vs chunk embeddings)
  3. LLM filter (keep/discard)
  4. Instruction generation per kept chunk
  5. Build FAISS index on instruction embeddings
"""
import sys
import json
import time
import numpy as np
import faiss
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CHUNKS_DIR, PERSONA_DIR, EPIC_INDEX_DIR, EMB_MODEL,
    COSINE_THRESHOLD, TOP_K, MBTI_TYPES,
)
from src.llm_client import call_llm


# ─── Embedding helpers ────────────────────────────────────────────────────────

_emb_tok = None
_emb_model = None
_emb_device = None

def _init_emb():
    global _emb_tok, _emb_model, _emb_device
    if _emb_model is not None:
        return
    import torch
    from transformers import AutoTokenizer, AutoModel
    _emb_tok = AutoTokenizer.from_pretrained(EMB_MODEL)
    _emb_model = AutoModel.from_pretrained(EMB_MODEL)
    _emb_model.eval()
    if torch.cuda.is_available():
        # CUDA_VISIBLE_DEVICES already remaps physical GPUs → use all visible
        _emb_device = "cuda:0"
        _emb_model = _emb_model.to(_emb_device)
        if torch.cuda.device_count() > 1:
            _emb_model = torch.nn.DataParallel(_emb_model)
            print(f"[emb] Using {torch.cuda.device_count()} GPUs via DataParallel")
    else:
        _emb_device = "cpu"
        _emb_model = _emb_model.to(_emb_device)


def embed_texts(texts: list[str], batch_size: int = 128) -> np.ndarray:
    import torch
    _init_emb()
    # DataParallel works best with larger batches — scale with GPU count
    if torch.cuda.is_available():
        batch_size = batch_size * torch.cuda.device_count()
    all_embs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        enc = _emb_tok(batch, padding=True, truncation=True, max_length=256, return_tensors="pt")
        enc = {k: v.to(_emb_device) for k, v in enc.items()}
        with torch.no_grad():
            out = _emb_model(**enc)
        # DataParallel returns output on cuda:0
        hidden = out.last_hidden_state if hasattr(out, "last_hidden_state") else out[0]
        mask = enc["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
        emb = (hidden * mask).sum(1) / mask.sum(1)
        emb = emb.cpu().numpy()
        emb = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
        all_embs.append(emb)
    return np.vstack(all_embs)


# ─── LLM prompts ──────────────────────────────────────────────────────────────

FILTER_SYSTEM = """\
You are a relevance filter for a personalized retrieval system.
Given a persona's preferences and a text chunk, decide whether the chunk
contains information that would meaningfully help generate a response
tailored to this persona's values and style."""

FILTER_USER = """\
Persona preferences:
{preferences}

Text chunk:
{chunk}

Does this chunk contain information relevant to at least one preference above?
Reply with exactly one of: Keep | Discard
Then on the next line give a one-sentence reason.

Format:
Decision: Keep
Reason: ..."""

INSTRUCTION_SYSTEM = """\
You are generating retrieval interpretation guidance for a personalized RAG system."""

INSTRUCTION_USER = """\
Persona preferences:
{preferences}

Relevant chunk:
{chunk}

Relevance reason: {reason}

Write a one-sentence instruction (≤30 words) telling the retrieval system
HOW to use this chunk when answering questions for this persona.
Start with an action verb. Be specific."""


def llm_filter_chunk(chunk_text: str, preferences_text: str) -> dict:
    prompt = FILTER_USER.format(preferences=preferences_text, chunk=chunk_text[:800])
    resp = call_llm(
        messages=[{"role": "user", "content": prompt}],
        system=FILTER_SYSTEM,
        max_tokens=80,
        temperature=0.0,
    )
    lines = resp.strip().splitlines()
    decision = "Keep" if "Keep" in lines[0] else "Discard"
    reason = lines[1].replace("Reason:", "").strip() if len(lines) > 1 else ""
    return {"decision": decision, "reason": reason}


def generate_instruction(chunk_text: str, preferences_text: str, reason: str) -> str:
    prompt = INSTRUCTION_USER.format(
        preferences=preferences_text,
        chunk=chunk_text[:600],
        reason=reason,
    )
    try:
        resp = call_llm(
            messages=[{"role": "user", "content": prompt}],
            system=INSTRUCTION_SYSTEM,
            max_tokens=60,
            temperature=0.3,
        )
        return resp.strip()
    except Exception as e:
        return f"Use this chunk to inform the response. ({e})"


# ─── Shared chunk embedding cache ────────────────────────────────────────────

_chunk_cache: dict = {}   # "chunks" → list[dict], "embs" → np.ndarray

def _load_chunks_and_embs(force: bool = False):
    """Load chunks + embeddings once; reuse across all MBTI types."""
    if _chunk_cache and not force:
        return _chunk_cache["chunks"], _chunk_cache["embs"]

    chunk_file = CHUNKS_DIR / "chunks.jsonl"
    emb_cache  = CHUNKS_DIR / "chunk_embs.npy"

    with open(chunk_file) as f:
        chunks = [json.loads(l) for l in f if l.strip()]
    print(f"[cache] Loaded {len(chunks)} chunks")

    if emb_cache.exists() and not force:
        print(f"[cache] Loading cached chunk embeddings from {emb_cache}")
        embs = np.load(str(emb_cache))
    else:
        print(f"[cache] Embedding {len(chunks)} chunks (this runs once)...")
        t0 = time.time()
        embs = embed_texts([c["text"] for c in chunks])
        np.save(str(emb_cache), embs)
        print(f"[cache] Embeddings saved → {emb_cache} ({time.time()-t0:.1f}s)")

    _chunk_cache["chunks"] = chunks
    _chunk_cache["embs"]   = embs
    return chunks, embs


# ─── vLLM connectivity check ─────────────────────────────────────────────────

def _check_vllm():
    from config import LLM_BACKEND, VLLM_URL
    if LLM_BACKEND != "vllm":
        return
    import requests
    try:
        r = requests.get(f"{VLLM_URL.rstrip('/v1')}/health", timeout=5)
        r.raise_for_status()
        print(f"[vllm] ✅ Server healthy at {VLLM_URL}")
    except Exception as e:
        raise RuntimeError(
            f"[vllm] ❌ Server not reachable at {VLLM_URL}: {e}\n"
            "Start it with: CUDA_VISIBLE_DEVICES=2,3 vllm serve Qwen/Qwen3-8B "
            "--tensor-parallel-size 2 --port 8008"
        )


# ─── Main indexing ────────────────────────────────────────────────────────────

def run_epic_indexing(mbti: str, force: bool = False, chunks=None, chunk_embs=None):
    out_dir = EPIC_INDEX_DIR / mbti
    out_dir.mkdir(parents=True, exist_ok=True)

    index_file = out_dir / "index.faiss"
    meta_file = out_dir / "kept.jsonl"

    if not force and index_file.exists() and meta_file.exists():
        print(f"[{mbti}] EPIC index already exists — skipping (use --force to rebuild)")
        return

    chunk_file = CHUNKS_DIR / "chunks.jsonl"
    if not chunk_file.exists():
        print(f"[{mbti}] No chunks file — run chunking first")
        return

    # Use pre-loaded shared embeddings if provided
    if chunks is None or chunk_embs is None:
        chunks, chunk_embs = _load_chunks_and_embs(force=force)
    print(f"[{mbti}] Using {len(chunks)} shared chunks")

    # Load preferences
    with open(PERSONA_DIR / "mbti_preferences.json") as f:
        all_prefs = json.load(f)
    prefs = all_prefs[mbti]["preferences"]
    preferences_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(prefs))

    t0 = time.time()
    print(f"[{mbti}] Embedding {len(prefs)} preferences...")
    pref_embs = embed_texts(prefs)
    emb_time = time.time() - t0
    print(f"[{mbti}] Preference embedding done in {emb_time:.1f}s")

    # Step 1: Cosine filter
    t1 = time.time()
    sims = np.dot(pref_embs, chunk_embs.T)  # (n_prefs, n_chunks)
    max_sims = sims.max(axis=0)
    cosine_mask = max_sims > COSINE_THRESHOLD
    kept_after_cosine = [c for c, keep in zip(chunks, cosine_mask) if keep]
    cosine_time = time.time() - t1
    print(f"[{mbti}] Cosine filter: {len(kept_after_cosine)}/{len(chunks)} kept in {cosine_time:.1f}s")

    # Step 2: LLM filter (parallel)
    t2 = time.time()
    llm_results = []
    with ThreadPoolExecutor(max_workers=64) as ex:
        futures = {
            ex.submit(llm_filter_chunk, c["raw_text"], preferences_text): c
            for c in kept_after_cosine
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"[{mbti}] LLM filter"):
            chunk = futures[fut]
            result = fut.result()
            llm_results.append((chunk, result))
    llm_time = time.time() - t2

    kept_after_llm = [
        (c, r) for c, r in llm_results if r["decision"] == "Keep"
    ]
    print(f"[{mbti}] LLM filter: {len(kept_after_llm)}/{len(kept_after_cosine)} kept in {llm_time:.1f}s")

    # Step 3: Instruction generation (parallel)
    t3 = time.time()
    instructions = []
    with ThreadPoolExecutor(max_workers=64) as ex:
        futures = {
            ex.submit(generate_instruction, c["raw_text"], preferences_text, r["reason"]): (c, r)
            for c, r in kept_after_llm
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc=f"[{mbti}] Instructions"):
            chunk, result = futures[fut]
            inst = fut.result()
            instructions.append({
                "chunk_id": chunk.get("chunk_id", ""),
                "text": chunk["raw_text"],
                "source": chunk.get("source", ""),
                "section": chunk.get("section", ""),
                "parent_url": chunk.get("parent_url", ""),
                "reason": result["reason"],
                "instruction": inst,
                "mbti": mbti,
            })
    inst_time = time.time() - t3
    print(f"[{mbti}] Instructions done in {inst_time:.1f}s")

    if not instructions:
        print(f"[{mbti}] No chunks survived filtering — index not built")
        return

    # Step 4: FAISS index on instruction embeddings
    t4 = time.time()
    inst_texts = [item["instruction"] for item in instructions]
    inst_embs = embed_texts(inst_texts)
    dim = inst_embs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(inst_embs.astype(np.float32))
    faiss.write_index(index, str(index_file))
    faiss_time = time.time() - t4

    with open(meta_file, "w") as f:
        for item in instructions:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    # Save stats
    stats = {
        "mbti": mbti,
        "total_chunks": len(chunks),
        "after_cosine": len(kept_after_cosine),
        "after_llm": len(kept_after_llm),
        "indexed": len(instructions),
        "emb_time_s": round(emb_time, 2),
        "cosine_time_s": round(cosine_time, 2),
        "llm_time_s": round(llm_time, 2),
        "inst_time_s": round(inst_time, 2),
        "faiss_time_s": round(faiss_time, 2),
        "total_time_s": round(time.time() - t0, 2),
    }
    with open(out_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"[{mbti}] ✅ EPIC index built: {len(instructions)} chunks, {stats['total_time_s']}s total")
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mbti", default="all")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    mbti_list = MBTI_TYPES if args.mbti == "all" else [args.mbti.upper()]
    for m in mbti_list:
        run_epic_indexing(m, force=args.force)
