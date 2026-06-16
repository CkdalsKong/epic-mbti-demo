# EPIC MBTI / PrefWiki Demo

Demos for **EPIC** (personalized memory indexing): an indexing pipeline that
turns raw documents into preference-aligned instruction memory, instead of
storing every chunk like plain RAG.

This repo has three demo surfaces, in the order they were built:

1. **`app.py`** — Streamlit demo over MBTI-type personas (original).
2. **`mac-app/`** — native macOS app, **Interactive EPIC** (see below).
3. **`server/`** — the backend the Mac app talks to, including the
   multi-GPU pre-indexing pipeline for the full corpus.

## Interactive EPIC (macOS app)

[`mac-app/`](mac-app) is forked from
[ginjae/InteractiveEPIC](https://github.com/ginjae/InteractiveEPIC) (live
EPIC-indexing visualization over a single Wikipedia article) and extends it
with a **Retrieval Demo** mode: load a persona's pre-indexed EPIC memory over
the *full* corpus (Wikipedia, Reddit, arXiv, …) and inspect retrieval —
memory footprint vs. Plain RAG, latency breakdown (query embedding vs. index
search), and query steering — without re-running indexing live.

```
mac-app/    SwiftUI app — see mac-app/README.md
server/     HTTP backend + corpus pre-indexing — see server/README.md
```

Quick start:

```bash
# On the GPU machine
cd server
python embed_corpus.py --corpus ./data/chunks/chunks.jsonl --out-dir ./preindex --gpus 0,1
python preindex_corpus.py --corpus ./data/chunks/chunks.jsonl --prefwiki ./dataset/PrefWiki.json \
  --out-dir ./preindex --llm-model meta-llama/Llama-3.1-8B-Instruct --llm-server-url http://127.0.0.1:8008
python epic_demo_server.py --llm-model meta-llama/Llama-3.1-8B-Instruct --llm-server-url http://127.0.0.1:8008 \
  --eval-llm-model meta-llama/Llama-3.3-70B-Instruct --eval-llm-server-url http://127.0.0.1:8009 \
  --preindex-dir ./preindex

# On your Mac, tunnel the server and build the app — see mac-app/README.md
```

See [`server/README.md`](server/README.md) and [`mac-app/README.md`](mac-app/README.md)
for full setup instructions.

## Streamlit demo (`app.py`)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Walks through EPIC indexing per MBTI persona against a shared corpus
collected with `src/collect_corpus.py` and chunked with `src/chunking.py`.
See `src/` for the indexing/generation/evaluation pipeline this demo is
built on (`src/epic_indexer.py`, etc.) — the same pipeline the Mac app's
`server/epic_runtime.py` is adapted from.

## Repo layout

```
app.py, config.py, src/      Streamlit MBTI demo (original)
data/                        Corpus, chunks, persona definitions (gitignored — large)
prompts/                     LLM prompt templates
mac-app/                     Interactive EPIC SwiftUI app
server/                      HTTP backend + corpus pre-indexing scripts for the Mac app
```
