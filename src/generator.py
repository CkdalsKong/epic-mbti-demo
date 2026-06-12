"""
Response generation for EPIC and Plain RAG.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import call_llm


SHARED_SYSTEM = """\
You are a helpful assistant. Answer the question using the retrieved documents below.
Give a thorough, practical response with specific advice. Use 3-5 paragraphs."""

SHARED_USER = """\
Retrieved documents:
{context}

Question: {question}"""


def format_epic_context(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        inst = doc.get("instruction", "")
        src = doc.get("source", "")
        text = doc["text"]
        header = f"[Doc {i}]"
        if src:
            header += f" ({src})"
        if inst:
            parts.append(f"{header}\nGuidance: {inst}\nContent: {text}")
        else:
            parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)


def format_rag_context(docs: list[dict]) -> str:
    return "\n\n".join(
        f"[Doc {i+1}] {d['text']}" for i, d in enumerate(docs)
    )


def generate_epic(
    query: str,
    mbti: str,
    mbti_meta: dict,
    docs: list[dict],
    backend: str | None = None,
) -> str:
    # Same prompt as RAG — difference is in the docs (instruction-augmented)
    context = format_epic_context(docs)
    user = SHARED_USER.format(context=context, question=query)
    return call_llm(
        messages=[{"role": "user", "content": user}],
        system=SHARED_SYSTEM,
        max_tokens=512,
        temperature=0.7,
        backend=backend,
    )


def generate_rag(
    query: str,
    docs: list[dict],
    backend: str | None = None,
) -> str:
    context = format_rag_context(docs)
    user = SHARED_USER.format(context=context, question=query)
    return call_llm(
        messages=[{"role": "user", "content": user}],
        system=SHARED_SYSTEM,
        max_tokens=512,
        temperature=0.7,
        backend=backend,
    )
