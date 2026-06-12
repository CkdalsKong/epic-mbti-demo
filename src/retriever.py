"""
Runtime retrieval for EPIC and Plain RAG.
Loads indices once and keeps them in memory.
"""
import sys
import json
import time
import numpy as np
import faiss
from pathlib import Path
from functools import lru_cache

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import EPIC_INDEX_DIR, RAG_INDEX_DIR, TOP_K, MBTI_TYPES
from src.epic_indexer import embed_texts


# ─── Index cache ──────────────────────────────────────────────────────────────

_epic_indices: dict = {}   # mbti → (faiss_index, list[dict])
_rag_index = None
_rag_chunks = None


def load_epic_index(mbti: str):
    if mbti in _epic_indices:
        return _epic_indices[mbti]
    index_file = EPIC_INDEX_DIR / mbti / "index.faiss"
    meta_file = EPIC_INDEX_DIR / mbti / "kept.jsonl"
    if not index_file.exists():
        return None, None
    index = faiss.read_index(str(index_file))
    with open(meta_file) as f:
        meta = [json.loads(l) for l in f if l.strip()]
    _epic_indices[mbti] = (index, meta)
    return index, meta


def load_rag_index():
    global _rag_index, _rag_chunks
    if _rag_index is not None:
        return _rag_index, _rag_chunks
    index_file = RAG_INDEX_DIR / "index.faiss"
    meta_file = RAG_INDEX_DIR / "chunks.jsonl"
    if not index_file.exists():
        return None, None
    _rag_index = faiss.read_index(str(index_file))
    with open(meta_file) as f:
        _rag_chunks = [json.loads(l) for l in f if l.strip()]
    return _rag_index, _rag_chunks


def _mb(path) -> float:
    """File size in MB, 0 if not found."""
    p = Path(path)
    return round(p.stat().st_size / 1024 / 1024, 1) if p.exists() else 0.0


def get_index_stats(mbti: str) -> dict:
    epic_index, epic_meta = load_epic_index(mbti)
    rag_index, rag_chunks = load_rag_index()

    stats_file = EPIC_INDEX_DIR / mbti / "stats.json"
    epic_stats = {}
    if stats_file.exists():
        with open(stats_file) as f:
            epic_stats = json.load(f)

    # File sizes
    epic_faiss_mb = _mb(EPIC_INDEX_DIR / mbti / "index.faiss")
    epic_meta_mb  = _mb(EPIC_INDEX_DIR / mbti / "kept.jsonl")
    rag_faiss_mb  = _mb(RAG_INDEX_DIR / "index.faiss")

    # GPU memory (if available)
    gpu_mem_mb = 0
    try:
        import torch
        if torch.cuda.is_available():
            gpu_mem_mb = round(torch.cuda.memory_allocated() / 1024 / 1024, 1)
    except Exception:
        pass

    return {
        "epic_indexed_chunks": len(epic_meta) if epic_meta else 0,
        "epic_total_input":    epic_stats.get("total_chunks", 0),
        "epic_after_cosine":   epic_stats.get("after_cosine", 0),
        "epic_after_llm":      epic_stats.get("after_llm", 0),
        "rag_total_chunks":    len(rag_chunks) if rag_chunks else 0,
        # Memory
        "epic_index_mb":       epic_faiss_mb,
        "epic_meta_mb":        epic_meta_mb,
        "epic_total_mb":       round(epic_faiss_mb + epic_meta_mb, 1),
        "rag_index_mb":        rag_faiss_mb,
        "gpu_mem_mb":          gpu_mem_mb,
    }


# ─── EPIC retrieval ───────────────────────────────────────────────────────────

def epic_retrieve(query: str, mbti: str, top_k: int = TOP_K) -> dict:
    index, meta = load_epic_index(mbti)
    if index is None:
        return {"error": f"EPIC index not found for {mbti}", "docs": [], "latency_ms": 0}

    # Load preferences for query augmentation
    from config import PERSONA_DIR
    with open(PERSONA_DIR / "mbti_preferences.json") as f:
        all_prefs = json.load(f)
    prefs = all_prefs[mbti]["preferences"]

    t0 = time.perf_counter()

    # Embed query
    query_emb = embed_texts([query])[0]

    # Find top matching preference → augment query
    pref_embs = embed_texts(prefs)
    pref_sims = np.dot(pref_embs, query_emb)
    top_pref = prefs[int(np.argmax(pref_sims))]

    aug_emb = query_emb + embed_texts([top_pref])[0]
    aug_emb = aug_emb / (np.linalg.norm(aug_emb) + 1e-9)

    # Search
    scores, idxs = index.search(aug_emb.reshape(1, -1).astype(np.float32), top_k)
    latency_ms = (time.perf_counter() - t0) * 1000

    docs = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or idx >= len(meta):
            continue
        item = meta[idx]
        docs.append({
            "text": item["text"],
            "instruction": item.get("instruction", ""),
            "source": item.get("source", ""),
            "section": item.get("section", ""),
            "url": item.get("parent_url", ""),
            "score": float(score),
        })

    return {
        "docs": docs,
        "top_preference": top_pref,
        "latency_ms": round(latency_ms, 1),
    }


# ─── Plain RAG retrieval ──────────────────────────────────────────────────────

def rag_retrieve(query: str, top_k: int = TOP_K) -> dict:
    index, chunks = load_rag_index()
    if index is None:
        return {"error": "RAG index not found", "docs": [], "latency_ms": 0}

    t0 = time.perf_counter()
    query_emb = embed_texts([query])[0]
    scores, idxs = index.search(query_emb.reshape(1, -1).astype(np.float32), top_k)
    latency_ms = (time.perf_counter() - t0) * 1000

    docs = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        c = chunks[idx]
        docs.append({
            "text": c.get("raw_text", c["text"]),
            "source": c.get("source", ""),
            "section": c.get("section", ""),
            "url": c.get("parent_url", ""),
            "score": float(score),
        })

    return {
        "docs": docs,
        "latency_ms": round(latency_ms, 1),
    }
