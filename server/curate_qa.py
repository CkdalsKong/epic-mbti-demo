#!/usr/bin/env python3
"""
Pre-compute and curate a fixed set of "known-good" demo questions per persona.

For each persona, this script:
  1. Loads the persona's pre-built EPIC + RAG index (preindex_corpus.py output).
  2. Builds a candidate pool per preference: PrefWiki's own ~5 queries PLUS
     --extra-questions-per-preference LLM-generated ones tailored to that
     exact preference (not generic) — round-robin across preferences so
     even a capped slice covers every preference at least once.
  3. Evaluates candidates in batches of --candidates-per-persona, topping up
     with more from the pool until --keep candidates pass (EPIC must have
     preference_following=True) or the pool is exhausted. A persona is never
     silently left with fewer curated questions than requested without a
     WARNING printed — check the output for personas that came up short.
  4. For each candidate: retrieves (EPIC + RAG), generates both responses,
     and runs the same 4-metric evaluation as the live demo
     (acknow / violate / hallucinate / helpful / preference_following).
  5. Ranks evaluated candidates by how clearly EPIC wins over Plain RAG, and
     keeps the top --keep per persona.
  6. Saves the full precomputed result (question, both responses, both doc
     lists, both eval results) to preindex/persona_N/curated_qa.json.

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
    --extra-questions-per-preference 10 \
    --candidates-per-persona 8 \
    --keep 3 \
    --workers 8
"""

import os

# Must be set BEFORE numpy/torch/transformers get imported (transitively,
# via epic_demo_server -> epic_runtime). Contriever runs on CPU here, and
# with --workers threads all calling encoder.encode() concurrently, each
# spawning its own multi-threaded OpenBLAS call, the OS runs out of mmap
# regions ("BLAS: Program is Terminated... too many memory regions" ->
# segfault). Capping each BLAS call to 1 thread fixes it — concurrency
# still comes from running --workers candidates in parallel, just without
# nested over-threading inside each one.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import argparse
import json
import re
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


QUESTION_GEN_SYSTEM = (
    "You generate realistic questions a user might ask an AI assistant. "
    "Output ONLY the questions, one per line, no numbering, no bullets, "
    "no preamble, no explanation."
)

QUESTION_GEN_USER = """The user has this preference: "{preference}"

Write {n} different, natural-sounding questions this user might ask an AI \
assistant in everyday situations where this preference would be relevant — \
but the questions themselves must NOT mention or hint at the preference. \
They should read like ordinary questions anyone could ask; the preference \
only matters once the assistant tries to answer.

Vary the phrasing and the specific scenario across questions. Output {n} \
questions, one per line, nothing else."""


def generate_extra_questions(state: EPICDemoState, preference: str, n: int) -> list[str]:
    """LLM-authored candidate questions tailored to one specific preference —
    expands the pool well beyond PrefWiki's fixed 5 queries per block."""
    if n <= 0:
        return []
    user_prompt = QUESTION_GEN_USER.format(preference=preference, n=n)
    try:
        reply = _generate_full(state, QUESTION_GEN_SYSTEM, user_prompt)
    except Exception as e:
        print(f"\n  [question-gen] LLM error: {e}", flush=True)
        return []

    lines = []
    for line in reply.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip any numbering/bullets the model adds despite instructions
        line = re.sub(r"^[\-\*\d]+[\.\)]?\s*", "", line).strip()
        if len(line) > 8:
            lines.append(line)
    return lines[:n]


def build_candidate_pool(state: EPICDemoState, persona_data: dict, extra_per_preference: int) -> list[dict]:
    """PrefWiki's own queries plus LLM-generated extras, round-robin across
    preferences so the early part of the pool already covers every
    preference at least once."""
    blocks = [b for b in persona_data["preference_blocks"] if b.get("preference")]
    if not blocks:
        return []

    per_block: list[list[dict]] = []
    for block in blocks:
        pref = block["preference"]
        own = [{"question": q["question"], "preference": pref} for q in block.get("queries", [])]
        extra_texts = generate_extra_questions(state, pref, extra_per_preference) if extra_per_preference > 0 else []
        extra = [{"question": q, "preference": pref} for q in extra_texts]
        per_block.append(own + extra)

    max_len = max((len(b) for b in per_block), default=0)
    out = []
    for qi in range(max_len):
        for block_questions in per_block:
            if qi < len(block_questions):
                out.append(block_questions[qi])
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
                        help="Batch size: evaluate this many candidates at a time, topping up "
                             "with more from the pool until --keep good ones are found or the "
                             "pool runs out")
    parser.add_argument("--extra-questions-per-preference", type=int, default=10,
                        help="LLM-generated extra candidate questions per preference, on top of "
                             "PrefWiki's own ~5 — set to 0 to use only PrefWiki's queries")
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

        print(f"  Building candidate pool (PrefWiki queries + "
              f"{args.extra_questions_per_preference} LLM-generated per preference)...", flush=True)
        all_candidates = build_candidate_pool(state, personas[pi], args.extra_questions_per_preference)
        if not all_candidates:
            print(f"  [{pi}] WARNING: persona has no preference_blocks — skipping", flush=True)
            continue

        # Evaluate in batches, topping up with more candidates until we
        # have `--keep` good ones (EPIC preference_following=True) or we
        # run out of available questions for this persona.
        results: list[dict] = []
        used = 0
        batch_size = args.candidates_per_persona
        t0 = time.time()
        while used < len(all_candidates):
            batch = all_candidates[used: used + batch_size]
            used += len(batch)
            print(f"  Evaluating candidates {used - len(batch) + 1}-{used} of {len(all_candidates)}...", flush=True)
            with tqdm(total=len(batch), desc=f"  p{pi} evaluating", unit="q") as pbar:
                with ThreadPoolExecutor(max_workers=args.workers) as ex:
                    futures = {ex.submit(evaluate_candidate, state, session, c): c for c in batch}
                    for fut in as_completed(futures):
                        try:
                            results.append(fut.result())
                        except Exception as e:
                            print(f"\n  [{pi}] candidate failed: {e}", flush=True)
                        pbar.update(1)

            good_so_far = sum(1 for r in results if score_candidate(r) > -100)
            if good_so_far >= args.keep:
                break
            if used < len(all_candidates):
                print(f"  Only {good_so_far}/{args.keep} good candidates so far — "
                      f"topping up with more questions...", flush=True)

        print(f"  Evaluated {len(results)} candidates total in {time.time()-t0:.1f}s "
              f"({used}/{len(all_candidates)} available questions used)", flush=True)

        scored = sorted(results, key=score_candidate, reverse=True)
        curated = [r for r in scored if score_candidate(r) > -100][: args.keep]

        if len(curated) < args.keep:
            print(f"  [{pi}] WARNING: only found {len(curated)}/{args.keep} good candidates "
                  f"after exhausting all {len(all_candidates)} available questions for this "
                  f"persona. This persona may need more PrefWiki queries, a lower bar in "
                  f"score_candidate(), or manual review.", flush=True)

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
