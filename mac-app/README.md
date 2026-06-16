# Interactive EPIC (macOS Demo App)

A native macOS SwiftUI app for demoing EPIC end-to-end. Originally forked from
[ginjae/InteractiveEPIC](https://github.com/ginjae/InteractiveEPIC), which only
visualized live EPIC indexing over a single Wikipedia article. This version adds
a second mode — **Retrieval Demo** — that runs against a pre-indexed, full-scale
corpus (Wikipedia, Reddit, arXiv, …) and breaks down retrieval latency, memory
footprint, and query steering between EPIC and Plain RAG.

The app talks to `server/epic_demo_server.py` (see [`../server`](../server)) over
HTTP at `http://127.0.0.1:8765`, normally reached through an SSH tunnel to the
GPU machine running the indexing/eval LLMs and the pre-built indexes.

## Two demo modes

On launch you choose one of two flows:

### 1. Indexing Demo
The original live-indexing walkthrough, unchanged in spirit:

`Preferences → Wikipedia → Chunking → Indexing → Results`

1. Pick a PrefWiki persona (or edit preferences).
2. Search and extract a Wikipedia page.
3. Chunk the document.
4. Run EPIC: coarse cosine filter → LLM fine verification → instruction
   generation, animated chunk-by-chunk.
5. Inspect the resulting EPIC memory vs. naive RAG memory: which chunks were
   kept, what instruction was generated, which preference it matches.

### 2. Retrieval Demo
Skips live indexing — loads a persona's **pre-built** EPIC index over the full
corpus (see [`server/preindex_corpus.py`](../server/preindex_corpus.py)) and
focuses on retrieval behavior:

`Persona → Retrieval Breakdown`

1. Pick a persona and load its pre-indexed EPIC memory (instant — no LLM calls).
2. See EPIC memory size vs. Plain RAG memory size side by side, with a reduction
   factor (e.g. "EPIC stores 47.9× less than Plain RAG").
3. Ask a question. Watch an animated retrieval pipeline: embed query → search →
   done.
4. See a **latency breakdown bar** per system in milliseconds — shared
   query-embedding time (gray) vs. each system's index-search time (teal for
   EPIC's small, preference-steered instruction index; orange for RAG's much
   larger raw chunk index) — plus the top-k retrieved docs, with EPIC's
   matched instruction shown alongside each doc (the "query steering" in
   action).

Generation (EPIC-RAG vs. Plain RAG, in parallel) and 4-metric evaluation
(acknowledge / violate / hallucinate / helpful) are implemented in the
codebase but currently hidden from the Retrieval Demo flow — see
`DemoStage.flow(for:)` in `InteractiveEPIC/ContentView.swift` to re-enable them.

## Runtime pieces

- **macOS app**: SwiftUI, `InteractiveEPIC.xcodeproj`
- **Demo server**: `../server/epic_demo_server.py`, reached at `http://127.0.0.1:8765`
- **Embedding model**: `facebook/contriever`
- **Vector index**: FAISS `IndexFlatIP`
- **Indexing LLM**: e.g. `meta-llama/Llama-3.1-8B-Instruct` via vLLM
- **Evaluation LLM**: e.g. `meta-llama/Llama-3.3-70B-Instruct` (FP8) via vLLM, separate port

## Connecting to the server

The server normally runs on a remote GPU machine. Tunnel it to your Mac:

```zsh
# 1. Forward the GPU pod's SSH port (example: behind a k8s pod)
kubectl port-forward -n <namespace> pod/<pod-name> 2222:22

# 2. Tunnel the demo server's port through that SSH connection
ssh <gpu-host-alias> -L 8765:localhost:8765
```

See [`../server/README.md`](../server/README.md) for how to start the server itself.

## Build & run

```zsh
cd mac-app
xcodebuild -scheme InteractiveEPIC -destination "platform=macOS" build \
  CODE_SIGNING_ALLOWED=NO CODE_SIGN_IDENTITY=""

# Run the built binary directly (avoids Launch Services issues in dev builds)
"$(xcodebuild -scheme InteractiveEPIC -showBuildSettings 2>/dev/null \
  | awk -F'= ' '/ TARGET_BUILD_DIR/{d=$2} / EXECUTABLE_PATH/{e=$2} END{print d"/"e}')" &
```

Or just open `InteractiveEPIC.xcodeproj` in Xcode and hit Run.

## Attribution

Forked from [ginjae/InteractiveEPIC](https://github.com/ginjae/InteractiveEPIC).
This version adds: the Retrieval Demo mode, `/load_persona` + `/retrieve`
server endpoints, the latency-breakdown and memory-comparison UI, and the
multi-GPU corpus pre-indexing pipeline in `../server/`.
