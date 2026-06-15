#!/usr/bin/env python3
"""
Pre-encode corpus chunks with Contriever using all available GPUs.

Run ONCE before preindex_corpus.py:

  python embed_corpus.py \
    --corpus ./data/chunks/chunks.jsonl \
    --out-dir ./server/preindex \
    --batch-size 512

Output:
  preindex/chunk_vectors.npy   — float32 (N, 768)
  preindex/rag_index.faiss     — IndexFlatIP over all chunks
  preindex/rag_chunks.json     — [{chunk_text, article_title}]

Multi-GPU: splits chunks evenly across GPUs, encodes in parallel,
then concatenates. On 2× H200, expect ~5-10 min for 750K chunks.
"""

import argparse
import json
import os
import sys
import time
from multiprocessing import Process, Queue

import faiss
import numpy as np

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# ── Per-GPU worker ─────────────────────────────────────────────────────────

def encode_worker(
    gpu_id: int,
    texts: list[str],
    model_name: str,
    batch_size: int,
    result_queue: Queue,
) -> None:
    import torch
    from transformers import AutoModel, AutoTokenizer

    device = torch.device(f"cuda:{gpu_id}")
    print(f"  [GPU {gpu_id}] Loading Contriever...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    model = AutoModel.from_pretrained(model_name, local_files_only=True)
    model = model.to(device).eval()
    print(f"  [GPU {gpu_id}] Encoding {len(texts)} chunks, batch={batch_size}...", flush=True)

    def mean_pooling(token_embeddings, mask):
        mask = mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)

    vectors = []
    t0 = time.time()
    with torch.inference_mode():
        for start in range(0, len(texts), batch_size):
            batch = texts[start: start + batch_size]
            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            outputs = model(**inputs)
            emb = mean_pooling(outputs.last_hidden_state, inputs["attention_mask"])
            emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            vectors.append(emb.cpu().numpy().astype("float32"))

            done = min(start + batch_size, len(texts))
            if done % (batch_size * 20) == 0 or done == len(texts):
                elapsed = time.time() - t0
                rate = done / elapsed
                eta = (len(texts) - done) / rate if rate > 0 else 0
                print(f"  [GPU {gpu_id}] {done}/{len(texts)} "
                      f"({rate:.0f} chunk/s, ETA {eta/60:.1f} min)", flush=True)

    result = np.vstack(vectors)
    print(f"  [GPU {gpu_id}] Done — {result.shape} in {(time.time()-t0)/60:.1f} min", flush=True)
    result_queue.put((gpu_id, result))


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-encode corpus with Contriever on all GPUs.")
    parser.add_argument("--corpus",     required=True, help="Path to corpus JSONL (chunks.jsonl)")
    parser.add_argument("--out-dir",    default="./preindex")
    parser.add_argument("--model",      default="facebook/contriever")
    parser.add_argument("--batch-size", type=int, default=512,
                        help="Per-GPU batch size (H200 can handle 512-1024)")
    parser.add_argument("--gpus",       default="all",
                        help="GPU ids to use, e.g. '0,1' or 'all'")
    args = parser.parse_args()

    import torch
    n_gpu = torch.cuda.device_count()
    if n_gpu == 0:
        print("No CUDA GPUs found — falling back to CPU (will be slow)")
        gpu_ids = []
    elif args.gpus == "all":
        gpu_ids = list(range(n_gpu))
    else:
        gpu_ids = [int(x) for x in args.gpus.split(",")]

    print(f"GPUs: {gpu_ids if gpu_ids else 'CPU'}", flush=True)

    os.makedirs(args.out_dir, exist_ok=True)

    out_vec   = os.path.join(args.out_dir, "chunk_vectors.npy")
    out_faiss = os.path.join(args.out_dir, "rag_index.faiss")
    out_meta  = os.path.join(args.out_dir, "rag_chunks.json")

    if os.path.exists(out_vec) and os.path.exists(out_faiss) and os.path.exists(out_meta):
        print(f"Cache already exists at {args.out_dir} — delete to re-encode.")
        print("  chunk_vectors.npy :", os.path.getsize(out_vec) // 1_000_000, "MB")
        print("  rag_index.faiss   :", os.path.getsize(out_faiss) // 1_000_000, "MB")
        return 0

    # Load corpus
    print(f"Loading corpus from {args.corpus}...", flush=True)
    t0 = time.time()
    chunks = []
    with open(args.corpus, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            display_text = obj.get("raw_text") or obj["text"]
            embed_text   = obj["text"]
            title = (
                obj.get("title") or obj.get("article_title")
                or f"{obj.get('source', '')} — {obj.get('topic', '')}".strip(" —")
                or ""
            )
            chunks.append({
                "index": i,
                "embed_text": embed_text,
                "display_text": display_text,
                "article_title": title,
            })
    print(f"  {len(chunks)} chunks loaded in {time.time()-t0:.1f}s", flush=True)

    embed_texts = [c["embed_text"] for c in chunks]

    # ── Encode ─────────────────────────────────────────────────────────────
    t0 = time.time()

    if not gpu_ids:
        # CPU fallback (single process)
        from transformers import AutoModel, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
        model = AutoModel.from_pretrained(args.model, local_files_only=True).eval()

        def mean_pooling(token_embeddings, mask):
            mask = mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            return torch.sum(token_embeddings * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)

        import torch
        vecs = []
        with torch.inference_mode():
            for start in range(0, len(embed_texts), args.batch_size):
                batch = embed_texts[start: start + args.batch_size]
                inputs = tokenizer(batch, padding=True, truncation=True,
                                   max_length=512, return_tensors="pt")
                out = model(**inputs)
                emb = mean_pooling(out.last_hidden_state, inputs["attention_mask"])
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
                vecs.append(emb.numpy().astype("float32"))
        chunk_vectors = np.vstack(vecs)
    else:
        # Split chunks across GPUs
        n = len(embed_texts)
        splits = []
        per_gpu = (n + len(gpu_ids) - 1) // len(gpu_ids)
        for i, gid in enumerate(gpu_ids):
            start = i * per_gpu
            end   = min(start + per_gpu, n)
            splits.append((gid, embed_texts[start:end]))

        result_queue: Queue = Queue()
        procs = []
        for gid, text_slice in splits:
            p = Process(
                target=encode_worker,
                args=(gid, text_slice, args.model, args.batch_size, result_queue),
                daemon=True,
            )
            p.start()
            procs.append(p)

        # Collect results in GPU order
        results: dict[int, np.ndarray] = {}
        for _ in procs:
            gid, arr = result_queue.get()
            results[gid] = arr
        for p in procs:
            p.join()

        chunk_vectors = np.vstack([results[gid] for gid, _ in splits])

    elapsed = time.time() - t0
    print(f"\nEncoding done: {len(chunk_vectors)} vectors in {elapsed/60:.1f} min "
          f"({len(chunk_vectors)/elapsed:.0f} chunk/s)", flush=True)

    # ── Save embeddings ────────────────────────────────────────────────────
    print(f"Saving {out_vec} ...", flush=True)
    np.save(out_vec, chunk_vectors)
    print(f"  {os.path.getsize(out_vec)//1_000_000} MB", flush=True)

    # ── Build & save RAG FAISS index ──────────────────────────────────────
    print("Building RAG FAISS index...", flush=True)
    dim = chunk_vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(chunk_vectors)
    faiss.write_index(index, out_faiss)
    idx_bytes = os.path.getsize(out_faiss)
    print(f"  RAG index: {idx_bytes//1_000_000} MB", flush=True)

    # ── Save RAG chunk metadata ────────────────────────────────────────────
    print(f"Saving {out_meta} ...", flush=True)
    rag_chunks = [
        {"chunk_text": c["display_text"], "article_title": c["article_title"]}
        for c in chunks
    ]
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(rag_chunks, f, ensure_ascii=False)
    print(f"  {os.path.getsize(out_meta)//1_000_000} MB", flush=True)

    print("\nAll done. Run preindex_corpus.py next — it will skip re-encoding.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
