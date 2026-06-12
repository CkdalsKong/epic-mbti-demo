"""
Plain RAG baseline index — shared across all MBTI types.
No persona filtering, no instructions. Just all chunks → FAISS.
"""
import sys
import json
import time
import numpy as np
import faiss
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CHUNKS_DIR, RAG_INDEX_DIR, MBTI_TYPES
from src.epic_indexer import embed_texts


def build_rag_index(force: bool = False):
    index_file = RAG_INDEX_DIR / "index.faiss"
    meta_file = RAG_INDEX_DIR / "chunks.jsonl"

    if not force and index_file.exists() and meta_file.exists():
        print("[RAG] Index already exists — skipping (use --force to rebuild)")
        return

    chunk_file = CHUNKS_DIR / "chunks.jsonl"
    if not chunk_file.exists():
        print("[RAG] chunks.jsonl not found — run chunking first")
        return

    all_chunks = []
    with open(chunk_file) as f:
        for line in f:
            if line.strip():
                all_chunks.append(json.loads(line))

    print(f"[RAG] Total chunks across all MBTI: {len(all_chunks)}")
    if not all_chunks:
        print("[RAG] No chunks found — run chunking first")
        return

    t0 = time.time()
    # Use raw_text (no context header) for RAG baseline — fair comparison
    texts = [c.get("raw_text", c["text"]) for c in all_chunks]
    print(f"[RAG] Embedding {len(texts)} chunks...")
    embs = embed_texts(texts)

    dim = embs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embs.astype(np.float32))
    faiss.write_index(index, str(index_file))

    with open(meta_file, "w") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0
    stats = {
        "total_chunks": len(all_chunks),
        "dim": dim,
        "build_time_s": round(elapsed, 2),
    }
    with open(RAG_INDEX_DIR / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"[RAG] ✅ Index built: {len(all_chunks)} chunks in {elapsed:.1f}s")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    build_rag_index(force=args.force)
