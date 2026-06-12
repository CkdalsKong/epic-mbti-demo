"""
Response generation for EPIC and Plain RAG.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.llm_client import call_llm


EPIC_SYSTEM = """\
You are a helpful assistant. You answer questions in a style and tone that matches
the user's personality type ({mbti} — {label}: {description}).
Use the retrieved documents below to ground your answer, applying the interpretation
guidance provided for each document.
Be specific and concrete. Match the voice and values of this personality type."""

EPIC_USER = """\
Personality: {mbti} ({label})

Retrieved documents:
{context}

Question: {question}

Answer in the voice and style of someone with the {mbti} personality type."""


RAG_SYSTEM = """\
You are a helpful assistant. Answer the question using only the retrieved documents below.
Be factual and concise."""

RAG_USER = """\
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
    context = format_epic_context(docs)
    system = EPIC_SYSTEM.format(
        mbti=mbti,
        label=mbti_meta["label"],
        description=mbti_meta["description"],
    )
    user = EPIC_USER.format(
        mbti=mbti,
        label=mbti_meta["label"],
        context=context,
        question=query,
    )
    return call_llm(
        messages=[{"role": "user", "content": user}],
        system=system,
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
    user = RAG_USER.format(context=context, question=query)
    return call_llm(
        messages=[{"role": "user", "content": user}],
        system=RAG_SYSTEM,
        max_tokens=512,
        temperature=0.3,
        backend=backend,
    )
