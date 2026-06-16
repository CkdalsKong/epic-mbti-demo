# EPIC Demo Server

HTTP server that backs the [Interactive EPIC macOS app](../mac-app). Runs on
the GPU machine (e.g. an H200 box) alongside vLLM and Contriever, and exposes
indexing / retrieval / generation / evaluation over a simple JSON + ndjson API.

## Endpoints

| Method | Path             | Streaming | Description |
|--------|------------------|-----------|--------------|
| GET    | `/health`        | no        | Server status, model names, session info |
| POST   | `/run`           | ndjson    | Run live EPIC indexing on a set of chunks (Indexing Demo) |
| POST   | `/load_persona`  | no        | Load a persona's **pre-built** EPIC + RAG index (Retrieval Demo) |
| POST   | `/retrieve`      | no        | Retrieval only — no generation. Returns docs, latency breakdown, memory stats |
| POST   | `/generate`      | ndjson    | Retrieve + generate EPIC-RAG and Plain RAG responses in parallel |
| POST   | `/evaluate`      | no        | 4-metric preference-following evaluation (acknow/violate/hallucinate/helpful) |

## Two LLMs

- **Indexing LLM** (`--llm-model` / `--llm-server-url`): used for EPIC's fine
  verification step and for generation. Small/fast, e.g. `Llama-3.1-8B-Instruct`.
- **Evaluation LLM** (`--eval-llm-model` / `--eval-llm-server-url`): used only
  by `/evaluate`. Larger/stronger, e.g. `Llama-3.3-70B-Instruct`. Falls back to
  the indexing LLM if not given.

These are deliberately separate vLLM servers (different ports) so a small
model can serve fast interactive indexing/generation while a large model
backs the evaluation judge.

## One-time setup: pre-index the corpus for the Retrieval Demo

The Retrieval Demo needs a pre-built EPIC + RAG index per PrefWiki persona,
built once over your full corpus. Two scripts, run in order:

### 1. `embed_corpus.py` — encode the corpus (multi-GPU)

```bash
python embed_corpus.py \
  --corpus  ./data/chunks/chunks.jsonl \
  --out-dir ./preindex \
  --batch-size 512 \
  --gpus 0,1
```

Splits chunks evenly across the given GPUs (one process per GPU, each with
its own model copy), encodes with Contriever, and writes:

- `preindex/chunk_vectors.npy` — float32 embeddings, shared by all personas
- `preindex/rag_index.faiss` — FAISS `IndexFlatIP` over all chunks (the Plain RAG index)
- `preindex/rag_chunks.json` — chunk text + article title, aligned to the index

On 2× H200 with ~750K chunks this takes a few minutes. Re-running with the
same `--out-dir` is a no-op if the cache already exists (delete the files to
force a re-encode).

### 2. `preindex_corpus.py` — per-persona EPIC indexing

```bash
python preindex_corpus.py \
  --corpus   ./data/chunks/chunks.jsonl \
  --prefwiki ./dataset/PrefWiki.json \
  --out-dir  ./preindex \
  --llm-model meta-llama/Llama-3.1-8B-Instruct \
  --llm-server-url http://127.0.0.1:8008 \
  --coarse-threshold 0.35 \
  --workers 64 \
  --resume
```

This faithfully replicates the real indexing pipeline
(`EPIC_indexing.py` + `EPIC_utils.py`), not a simplified stand-in:

1. **Coarse cosine filter** — a chunk is kept if it exceeds
   `--coarse-threshold` against *any* preference. Every preference that
   matched is tracked (not just the best one), because step 2 only shows
   the LLM the preferences that already passed here.
2. **Fine LLM filtering** — uses the actual `prompts/filtering_*.txt`
   templates (XML `<decision>`/`<reason>`/`<relevant_preferences>`), shown
   only the chunk's coarse-matched preferences, shuffled with a seed derived
   from the chunk index (matches `process_chunk_rand_prefs` exactly).
3. **Instruction generation** — a *separate* LLM call using
   `prompts/instruction_*.txt`, fed the filtering step's `<reason>` plus the
   matched preferences. This generated instruction — not the raw chunk — is
   what gets embedded into the EPIC FAISS index.

Each kept chunk costs 2 LLM calls (filter, then instruction) instead of 1.
`--workers` threads hit vLLM concurrently (vLLM batches internally, so
32–128 is reasonable depending on GPU headroom).

`--resume` skips personas that already have a `meta.json` (useful for
re-running after a partial failure or to add more personas later — delete
a `persona_N/` dir to force that one to rebuild).

Output layout:

```
preindex/
  chunk_vectors.npy        # shared embeddings
  rag_index.faiss          # shared RAG index
  rag_chunks.json          # shared RAG chunk metadata
  persona_0/
    epic_index.faiss       # this persona's EPIC instruction index
    epic_entries.json      # chunk_text, article_title, instruction, preference, reason per entry
    meta.json              # counts, byte sizes, rag_index_path (points at the shared file above)
  persona_1/ ...
  persona_56/ ...
```

The RAG index is **not** duplicated per persona — `meta.json` stores an
absolute path back to the shared `rag_index.faiss` (saves ~130 GB across 57
personas on a 750K-chunk corpus).

## Running the server

```bash
python epic_demo_server.py \
  --llm-model meta-llama/Llama-3.1-8B-Instruct \
  --llm-server-url http://127.0.0.1:8008 \
  --eval-llm-model meta-llama/Llama-3.3-70B-Instruct \
  --eval-llm-server-url http://127.0.0.1:8009 \
  --preindex-dir ./preindex
```

Starts at `http://127.0.0.1:8765`. Tunnel that port to your Mac (see the
[mac-app README](../mac-app/README.md)) before launching the app.

### vLLM setup

```bash
# Indexing / generation LLM (small, fast)
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8008

# Evaluation LLM (large, FP8 to fit on a single H200)
vllm serve meta-llama/Llama-3.3-70B-Instruct \
  --port 8009 \
  --quantization fp8 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 4096
```

FP8 on Llama 3.3 70B is within ~1% of BF16 on standard benchmarks — safe for
a demo judge model, and the only way a 70B model fits comfortably on one
H200 (140 GB) alongside the 8B model.

## Files

- `epic_runtime.py` — core EPIC pipeline (Contriever encoder, coarse filter,
  LLM fine verification, ndjson event emission). Shared with the live
  Indexing Demo (`/run`).
- `epic_demo_server.py` — this HTTP server.
- `embed_corpus.py` — multi-GPU corpus embedding (step 1 above).
- `preindex_corpus.py` — per-persona EPIC indexing over the cached embeddings (step 2 above).
- `prompts/` — the real filtering and instruction-generation prompts, copied
  verbatim from the EPIC pipeline (`filtering_systemprompt.txt`,
  `filtering_userprompt.txt`, `instruction_systemprompt.txt`,
  `instruction_userprompt.txt`). `preindex_corpus.py` loads these directly —
  don't edit them without checking they still match the upstream pipeline.
