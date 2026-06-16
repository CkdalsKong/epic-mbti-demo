#!/usr/bin/env python3
"""
Pre-compute and curate a fixed set of "known-good" demo questions per persona.

For each persona, this script:
  1. Loads the persona's pre-built EPIC + RAG index (preindex_corpus.py output).
  2. Takes candidate questions from PrefWiki's preference_blocks[*].queries.
  3. For each candidate: retrieves (EPIC + RAG), generates both responses,
     and runs the same 4-metric evaluation as the live demo
     (acknow / violate / hallucinate / helpful / preference_following).
  4. Ranks candidates by how clearly EPIC wins over Plain RAG, and keeps the
     top N per persona.
  5. Saves the full precomputed result (question, both responses, both doc
     lists, both eval results, retrieval latency) to
     preindex/persona_N/curated_qa.json.

The demo app then loads these via GET /curated_questions — instant, no LLM
calls during the live demo, and every question shown is one we've already
verified produces a good EPIC vs Plain RAG contrast.

Run once after preindex_corpus.py, on the same machine as the vLLM servers:

  python curate_qa.py \
    --preindex-dir ./preindex \
    --prefwiki ./dataset/PrefWiki.json \
    --llm-model meta-llama/Llama-3.1-8B-Instruct \
    --llm-server-url http://127.0.0.1:8008 \
    --eval-llm-model meta-llama/Llama-3.3-70B-Instruct \
    --eval-llm-server-url http://127.0.0.1:8009 \
    --personas 0-56 \
    --candidates-per-persona 8 \
    --keep 3 \
    --workers 8
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

# Reuse everything from the demo server — same retrieval/generation/eval code
# paths as the live app, so curated results are guaranteed to match.
sys.path.insert(0, os.path.dirname(__file__))
from epic_demo_server import (
    CONTRIEVER_MODEL,
    EPIC_GEN_SYSTEM,
    RAG_GEN_SYSTEM,
    ContrieverEncoder,
    EPICDemoState,
    build_epic_context,
    build_rag_context,
    epic_retrieve,
    evaluate_single,
    load_persona_session,
    rag_retrieve,
)
from epic_demo_server import _generate_full  # non-streaming generation


def load_prefwiki(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_persona_range(spec: str, total: int) -> list[int]:
    indices = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            indices.update(range(int(a), int(b) + 1))
        else:
            indices.add(int(part))
    return sorted(i for i in indices if 0 <= i < total)


def candidate_questions(persona_data: dict, max_candidates: int) -> list[dict]:
    """One question per preference block (its first query), up to max_candidates."""
    out = []
    for block in persona_data["preference_blocks"]:
        queries = block.get("queries", [])
        if not queries:
            continue
        out.append({"question": queries[0]["question"], "preference": block["preference"]})
        if len(out) >= max_candidates:
            break
    return out


def evaluate_candidate(state: EPICDemoState, session, candidate: dict, top_k: int = 5) -> dict:
    question = candidate["question"]
    preference = candidate["preference"]

    epic_docs = epic_retrieve(state, session, question, top_k)
    rag_docs = rag_retrieve(state, session, question, top_k)

    epic_context = build_epic_context(epic_docs)
    epic_user = f"Retrieved documents:\n{epic_context}\n\nQuestion: {question}"
    rag_context = build_rag_context(rag_docs)
    rag_user = f"Retrieved documents:\n{rag_context}\n\nQuestion: {question}"

    with ThreadPoolExecutor(max_workers=2) as ex:
        epic_fut = ex.submit(_generate_full, state, EPIC_GEN_SYSTEM, epic_user)
        rag_fut = ex.submit(_generate_full, state, RAG_GEN_SYSTEM, rag_user)
        epic_response = epic_fut.result()
        rag_response = rag_fut.result()

    with ThreadPoolExecutor(max_workers=2) as ex:
        epic_eval_fut = ex.submit(evaluate_single, state, question, preference, epic_response)
        rag_eval_fut = ex.submit(evaluate_single, state, question, preference, rag_response)
        epic_eval = epic_eval_fut.result()
        rag_eval = rag_eval_fut.result()

    return {
        "question": question,
        "preference": preference,
        "epic_response": epic_response,
        "rag_response": rag_response,
        "epic_docs": epic_docs,
        "rag_docs": rag_docs,
        "epic_eval": epic_eval,
        "rag_eval": rag_eval,
    }


def score_candidate(result: dict) -> int:
    """Higher = better demo material: EPIC should follow the preference;
    extra credit if Plain RAG visibly fails where EPIC succeeds (the
    contrast is the whole point of the demo)."""
    epic_pf = result["epic_eval"]["preference_following"]
    rag_pf = result["rag_eval"]["preference_following"]
    if not epic_pf:
        return -100  # never show a question where EPIC itself fails
    score = 10
    if not rag_pf:
        score += 10  # EPIC wins, RAG fails — the ideal demo case
    if result["epic_eval"]["acknow"]:
        score += 2
    if not result["epic_eval"]["hallucinate"]:
        score += 1
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-compute curated demo Q&A per persona.")
    parser.add_argument("--preindex-dir", required=True, help="Directory from preindex_corpus.py")
    parser.add_argument("--prefwiki",     required=True, help="Path to PrefWiki.json")
    parser.add_argument("--llm-model",      default="meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--llm-server-url", default="http://127.0.0.1:8008")
    parser.add_argument("--eval-llm-model",      default="")
    parser.add_argument("--eval-llm-server-url", default="")
    parser.add_argument("--llm-timeout", type=int, default=120)
    parser.add_argument("--personas", default="0-56")
    parser.add_argument("--candidates-per-persona", type=int, default=8,
                        help="How many candidate questions to try per persona before curating")
    parser.add_argument("--keep", type=int, default=3, help="How many curated questions to keep per persona")
    parser.add_argument("--workers", type=int, default=8, help="Parallel candidates evaluated at once")
    parser.add_argument("--resume", action="store_true", help="Skip personas that already have curated_qa.json")
    args = parser.parse_args()

    print("Loading Contriever...", flush=True)
    encoder = ContrieverEncoder(CONTRIEVER_MODEL)
    encoder.encode(["warmup"])
    print(f"  ready (dim={encoder.dimension})", flush=True)

    state = EPICDemoState(
        encoder=encoder,
        llm_model=args.llm_model,
        llm_server_url=args.llm_server_url,
        llm_timeout=args.llm_timeout,
        eval_llm_model=args.eval_llm_model,
        eval_llm_server_url=args.eval_llm_server_url,
        preindex_dir=args.preindex_dir,
    )
    print(f"Indexing/Gen LLM : {state.llm_model} @ {state.llm_server_url}", flush=True)
    print(f"Eval LLM         : {state.eval_llm_model} @ {state.eval_llm_server_url}", flush=True)

    personas = load_prefwiki(args.prefwiki)
    persona_indices = parse_persona_range(args.personas, len(personas))
    print(f"Will curate personas: {persona_indices}", flush=True)

    for pi in persona_indices:
        out_path = os.path.join(args.preindex_dir, f"persona_{pi}", "curated_qa.json")
        if args.resume and os.path.exists(out_path):
            print(f"\n[{pi}] Skipping (curated_qa.json exists)", flush=True)
            continue

        print(f"\n[{pi}] Loading session...", flush=True)
        try:
            session = load_persona_session(state, pi)
        except Exception as e:
            print(f"  [{pi}] Failed to load session: {e}", flush=True)
            continue

        candidates = candidate_questions(personas[pi], args.candidates_per_persona)
        print(f"  {len(candidates)} candidate questions", flush=True)

        results = []
        t0 = time.time()
        with tqdm(total=len(candidates), desc=f"  p{pi} evaluating", unit="q") as pbar:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = {ex.submit(evaluate_candidate, state, session, c): c for c in candidates}
                for fut in as_completed(futures):
                    try:
                        results.append(fut.result())
                    except Exception as e:
                        print(f"\n  [{pi}] candidate failed: {e}", flush=True)
                    pbar.update(1)
        print(f"  Evaluated {len(results)} candidates in {time.time()-t0:.1f}s", flush=True)

        scored = sorted(results, key=score_candidate, reverse=True)
        curated = [r for r in scored if score_candidate(r) > -100][: args.keep]

        if not curated:
            print(f"  [{pi}] WARNING: no candidate had EPIC preference_following=True — "
                  f"saving empty curated_qa.json. Consider raising --candidates-per-persona.", flush=True)

        win_count = sum(1 for r in curated if not r["rag_eval"]["preference_following"])
        print(f"  Kept {len(curated)}/{len(results)} ({win_count} where RAG fails and EPIC succeeds)", flush=True)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(curated, f, ensure_ascii=False, indent=2)
        print(f"  Saved to {out_path}", flush=True)

    print("\nAll done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
