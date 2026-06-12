"""
Full offline pipeline orchestrator.
Run this on the server BEFORE the demo.

Steps:
  1. collect  — scrape corpus from all sources
  2. chunk    — semantic chunking + contextual augmentation
  3. index    — EPIC indexing (16 MBTI types) + RAG indexing
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import MBTI_TYPES


def step_collect(sources, parallel=True):
    from src.collect_corpus import collect
    print(f"\n{'='*60}")
    print("STEP 1: Corpus Collection (shared corpus)")
    print(f"{'='*60}")
    collect(sources, parallel=parallel)


def step_chunk():
    from src.chunking import run_chunking
    print(f"\n{'='*60}")
    print("STEP 2: Semantic Chunking (shared corpus)")
    print(f"{'='*60}")
    run_chunking()


def step_index_epic(mbti_list, force):
    from src.epic_indexer import run_epic_indexing, _load_chunks_and_embs, _check_vllm
    print(f"\n{'='*60}")
    print("STEP 3a: EPIC Indexing")
    print(f"{'='*60}")
    _check_vllm()
    print("\n[epic] Pre-loading shared chunk embeddings (once for all MBTI types)...")
    chunks, chunk_embs = _load_chunks_and_embs(force=force)
    for mbti in mbti_list:
        run_epic_indexing(mbti, force=force, chunks=chunks, chunk_embs=chunk_embs)


def step_index_rag(force):
    from src.rag_indexer import build_rag_index
    print(f"\n{'='*60}")
    print("STEP 3b: Plain RAG Indexing (baseline)")
    print(f"{'='*60}")
    build_rag_index(force=force)


def main():
    parser = argparse.ArgumentParser(description="EPIC MBTI Demo — offline pipeline")
    parser.add_argument(
        "--steps", default="all",
        help="Comma-separated: collect,chunk,index_epic,index_rag  or 'all'",
    )
    parser.add_argument("--mbti", default="all", help="MBTI type or 'all'")
    parser.add_argument(
        "--sources", default="16p,psytoday,thoughtcatalog,namuwiki,genre",
        help="Corpus sources (comma-separated). Add 'reddit' if credentials available.",
    )
    parser.add_argument("--force", action="store_true", help="Rebuild even if outputs exist")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel collection (for debugging)")
    args = parser.parse_args()

    all_steps = ["collect", "chunk", "index_epic", "index_rag"]
    steps = all_steps if args.steps == "all" else args.steps.split(",")
    mbti_list = MBTI_TYPES if args.mbti == "all" else [args.mbti.upper()]
    sources = args.sources.split(",")

    print(f"Pipeline config:")
    print(f"  Steps:   {steps}")
    print(f"  MBTI:    {mbti_list}")
    print(f"  Sources: {sources}")
    print(f"  Force:   {args.force}")

    if "collect" in steps:
        step_collect(sources, parallel=not args.no_parallel)
    if "chunk" in steps:
        step_chunk()
    if "index_epic" in steps:
        step_index_epic(mbti_list, args.force)
    if "index_rag" in steps:
        step_index_rag(args.force)

    print(f"\n{'='*60}")
    print("Pipeline complete! Run the demo with:")
    print("  streamlit run app.py")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
