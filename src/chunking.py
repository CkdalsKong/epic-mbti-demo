"""
Semantic chunking with contextual augmentation.

Strategy:
1. Split text into sentences
2. Embed sentences with a lightweight model
3. Merge adjacent sentences until cosine similarity drops below threshold
4. Prepend [source / MBTI / topic] context to each chunk before final embedding
   → preserves cross-chunk meaning that fixed-size splits lose
"""

import re
import sys
import json
import numpy as np
from tqdm import tqdm
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    CORPUS_DIR, CHUNKS_DIR, MBTI_TYPES,
    CHUNK_SIZE, CHUNK_OVERLAP, SEMANTIC_THRESHOLD,
    EMB_MODEL,
)


def _load_emb_model():
    import torch
    from transformers import AutoTokenizer, AutoModel
    tok = AutoTokenizer.from_pretrained(EMB_MODEL)
    model = AutoModel.from_pretrained(EMB_MODEL)
    model.eval()
    if torch.cuda.is_available():
        device = "cuda:0"
        model = model.to(device)
        if torch.cuda.device_count() > 1:
            model = torch.nn.DataParallel(model)
            print(f"[chunking] Using {torch.cuda.device_count()} GPUs via DataParallel")
    else:
        device = "cpu"
        model = model.to(device)
    return tok, model, device


def _mean_pool(model_output, attention_mask):
    import torch
    token_embs = model_output.last_hidden_state
    mask = attention_mask.unsqueeze(-1).expand(token_embs.size()).float()
    return (token_embs * mask).sum(1) / mask.sum(1)


def embed_sentences(sentences: list[str], tok, model, device: str) -> np.ndarray:
    import torch
    batch_size = 128 * max(1, torch.cuda.device_count()) if torch.cuda.is_available() else 64
    all_embs = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]
        enc = tok(batch, padding=True, truncation=True, max_length=128, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            out = model(**enc)
        hidden = out.last_hidden_state if hasattr(out, "last_hidden_state") else out[0]
        mask = enc["attention_mask"].unsqueeze(-1).expand(hidden.size()).float()
        embs = ((hidden * mask).sum(1) / mask.sum(1)).cpu().numpy()
        embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9)
        all_embs.append(embs)
    return np.vstack(all_embs)


def split_sentences(text: str) -> list[str]:
    # Simple rule-based splitter (fast, no NLTK needed)
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z가-힣])", text)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def semantic_chunk(
    text: str,
    tok, model, device: str,
    threshold: float = SEMANTIC_THRESHOLD,
    max_words: int = CHUNK_SIZE,
    overlap_words: int = CHUNK_OVERLAP,
) -> list[str]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) == 1:
        return sentences

    embs = embed_sentences(sentences, tok, model, device)

    # Compute consecutive cosine similarities
    sims = np.array([
        float(np.dot(embs[i], embs[i + 1]))
        for i in range(len(embs) - 1)
    ])

    # Find split points: where similarity drops below threshold
    split_idxs = [0] + [i + 1 for i, s in enumerate(sims) if s < threshold] + [len(sentences)]

    chunks = []
    for start, end in zip(split_idxs[:-1], split_idxs[1:]):
        group = sentences[start:end]
        # Further split if too long
        buf, word_count = [], 0
        for sent in group:
            wc = len(sent.split())
            if word_count + wc > max_words and buf:
                chunks.append(" ".join(buf))
                # overlap: keep last overlap_words worth of sentences
                overlap_buf, ow = [], 0
                for s in reversed(buf):
                    sw = len(s.split())
                    if ow + sw > overlap_words:
                        break
                    overlap_buf.insert(0, s)
                    ow += sw
                buf, word_count = overlap_buf, ow
            buf.append(sent)
            word_count += wc
        if buf:
            chunks.append(" ".join(buf))

    return [c for c in chunks if len(c.strip()) > 30]


def build_contextual_chunk(
    chunk_text: str,
    source: str,
    topic: Optional[str] = None,
) -> str:
    """
    Prepend [Source / Topic] header so the embedding captures document-level
    context (Anthropic contextual retrieval idea). No MBTI tag here —
    the same chunk pool is shared; EPIC personalizes at index time.
    """
    parts = [f"[Source: {source}]"]
    if topic:
        parts.append(f"[Topic: {topic}]")
    return " ".join(parts) + "\n" + chunk_text


def process_shared_corpus(tok, model, device: str) -> list[dict]:
    """Chunk the shared corpus.jsonl once — result is shared by all MBTI types."""
    corpus_file = CORPUS_DIR / "corpus.jsonl"
    if not corpus_file.exists():
        print("  [chunking] corpus.jsonl not found — run collect first")
        return []

    with open(corpus_file) as f:
        docs = [json.loads(l) for l in f if l.strip()]
    print(f"  [chunking] {len(docs)} docs → chunking...")

    chunks_out = []
    for doc_idx, doc in enumerate(tqdm(docs, desc="chunking")):
        text = doc.get("text", "")
        if len(text) < 50:
            continue
        source = doc.get("source", "unknown")
        topic = doc.get("topic", "")

        raw_chunks = semantic_chunk(text, tok, model, device)
        for i, chunk in enumerate(raw_chunks):
            contextual = build_contextual_chunk(chunk, source, topic)
            chunks_out.append({
                "chunk_id": f"doc{doc_idx}_chunk{i}",
                "source": source,
                "topic": topic,
                "raw_text": chunk,     # for LLM context / display
                "text": contextual,    # for embedding
                "parent_url": doc.get("url", ""),
            })

    return chunks_out


def save_shared_chunks(chunks: list[dict]):
    out_file = CHUNKS_DIR / "chunks.jsonl"
    with open(out_file, "w") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  [chunking] {len(chunks)} chunks → {out_file}")


def run_chunking():
    out_file = CHUNKS_DIR / "chunks.jsonl"
    if out_file.exists():
        count = sum(1 for _ in open(out_file) if _.strip())
        print(f"[chunking] chunks.jsonl already exists ({count} chunks) — skipping (delete to rebuild)")
        return

    print("Loading embedding model for semantic splitting...")
    tok, model, device = _load_emb_model()
    chunks = process_shared_corpus(tok, model, device)
    if chunks:
        save_shared_chunks(chunks)
    else:
        print("[chunking] No chunks produced")


if __name__ == "__main__":
    run_chunking()
