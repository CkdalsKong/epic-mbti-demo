#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Callable

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

import faiss


CONTRIEVER_MODEL = "facebook/contriever"
VLLM_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
VLLM_SERVER_URL = "http://127.0.0.1:8123"


def mean_pooling(token_embeddings: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    mask = mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    summed = torch.sum(token_embeddings * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts


class ContrieverEncoder:
    def __init__(self, model_name: str = CONTRIEVER_MODEL):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
        self.model = AutoModel.from_pretrained(model_name, local_files_only=True)
        self.model.eval()
        self.dimension = int(self.model.config.hidden_size)

    @torch.inference_mode()
    def encode(
        self,
        texts: list[str],
        batch_size: int = 16,
        on_batch: Callable[[int, int], None] | None = None,
    ) -> np.ndarray:
        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            inputs = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            outputs = self.model(**inputs)
            embeddings = mean_pooling(outputs.last_hidden_state, inputs["attention_mask"])
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            vectors.append(embeddings.cpu().numpy().astype("float32"))
            if on_batch is not None:
                on_batch(min(start + batch_size, len(texts)), len(texts))
        if not vectors:
            return np.zeros((0, self.dimension), dtype="float32")
        return np.vstack(vectors)


def emit_event(args: argparse.Namespace, event: str, **payload: Any) -> None:
    event_payload = {"event": event, **payload}
    event_sink = getattr(args, "event_sink", None)
    if event_sink is not None:
        event_sink(event_payload)
        return
    if not getattr(args, "events", False):
        return
    json.dump(event_payload, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def build_index(vectors: np.ndarray) -> tuple[faiss.IndexFlatIP, int]:
    if vectors.ndim != 2:
        raise ValueError("Expected a 2-D embedding matrix.")
    dimension = vectors.shape[1] if vectors.shape[0] else 768
    index = faiss.IndexFlatIP(dimension)
    if vectors.shape[0]:
        index.add(vectors)
    serialized = faiss.serialize_index(index)
    return index, int(len(serialized))


def text_bytes(texts: list[str]) -> int:
    return sum(len(text.encode("utf-8")) for text in texts)


def preference_kind(preference: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", preference.lower())
    if "electric vehicles" in normalized:
        return "electricVehicles"
    if "pickup trucks" in normalized:
        return "pickupTrucks"
    if "european car brands" in normalized:
        return "europeanCars"
    if "backtracking" in normalized:
        return "repetitiveGames"
    if "raw vegan" in normalized:
        return "rawVegan"
    if "gimmicky dining" in normalized or "quality food" in normalized:
        return "restaurantQuality"
    if "spicy food" in normalized:
        return "spicyFood"
    if "strict vegan" in normalized or "animal derived" in normalized:
        return "vegan"
    if "shelters" in normalized or "breeders" in normalized:
        return "shelterPets"
    if "scratchy" in normalized or "wool" in normalized:
        return "textureSensitive"
    return "generic"


def extract_json(text: str) -> dict[str, Any]:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    text = text.replace("\x08", "")
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", text))):
        snippet = text[match.start() :]
        try:
            value, _ = decoder.raw_decode(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "decision" in value:
            return value

    raise ValueError(f"LLM did not return a valid decision JSON object: {text[-700:]}")


def llama_prompt(chunk: dict[str, Any], matches: list[dict[str, Any]]) -> str:
    preferences = "\n".join(
        f"- [{match['preference_index']}] cosine={match['score']:.4f}: {match['preference']}"
        for match in matches
    )
    return f"""You are EPIC's Preference-Aligned Fine Verification module.

Decide whether the chunk should be retained for preference-aligned on-device memory.
Use only the listed user preferences. Do not infer unstated preferences.

Return valid JSON only with this schema:
{{
  "decision": "Keep" or "Discard",
  "rationale": "brief reason",
  "relevant_preferences": [integer preference indexes],
  "instructions": [
    {{"preference_index": integer, "instruction": "concise usage instruction"}}
  ]
}}

Rules:
- Keep only if the chunk is genuinely useful for at least one listed preference.
- Discard if the chunk is only topically adjacent or has no actionable preference relevance.
- Each instruction should say how to use the chunk for future preference-aligned answers.

Candidate preferences:
{preferences}

Chunk {chunk['index']} from "{chunk['article_title']}":
{chunk['text']}
"""


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_data = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        error_data = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned HTTP {error.code}: {error_data}") from error
    return json.loads(response_data)


def run_llama_server(prompt: str, server_url: str, model: str, timeout: int) -> dict[str, Any]:
    base_url = server_url.rstrip("/")
    chat_payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 512,
        "seed": 7,
        "response_format": {"type": "json_object"},
    }
    response = post_json(f"{base_url}/v1/chat/completions", chat_payload, timeout)
    content = response["choices"][0]["message"]["content"]
    return extract_json(content)


def run_llama(
    prompt: str,
    timeout: int,
    server_url: str | None = None,
    model: str = VLLM_MODEL,
) -> dict[str, Any]:
    return run_llama_server(prompt, server_url or VLLM_SERVER_URL, model, timeout)


def verify_with_llm(
    chunks_by_index: dict[int, dict[str, Any]],
    coarse_candidates: list[dict[str, Any]],
    timeout: int,
    server_url: str | None = None,
    model: str = VLLM_MODEL,
    emit: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    evaluations: list[dict[str, Any]] = []
    total = len(coarse_candidates)
    for candidate_position, candidate in enumerate(coarse_candidates):
        chunk = chunks_by_index[candidate["chunk_index"]]
        if emit is not None:
            emit(
                "fine_chunk_started",
                chunk_index=int(chunk["index"]),
                completed_fine=candidate_position,
                total_fine=total,
            )
        evaluation = evaluate_candidate_with_llm(
            chunks_by_index,
            candidate,
            timeout,
            server_url=server_url,
            model=model,
        )
        evaluations.append(evaluation)
        if emit is not None:
            emit(
                "fine_chunk_finished",
                chunk_index=int(chunk["index"]),
                completed_fine=candidate_position + 1,
                total_fine=total,
                fine_evaluation=evaluation,
            )
    return evaluations


def evaluate_candidate_with_llm(
    chunks_by_index: dict[int, dict[str, Any]],
    candidate: dict[str, Any],
    timeout: int,
    server_url: str | None = None,
    model: str = VLLM_MODEL,
) -> dict[str, Any]:
    chunk = chunks_by_index[candidate["chunk_index"]]
    matches = candidate["matches"]
    response = run_llama(
        llama_prompt(chunk, matches),
        timeout,
        server_url=server_url,
        model=model,
    )

    decision = str(response.get("decision", "Discard")).strip()
    relevant_indexes = {
        int(index)
        for index in response.get("relevant_preferences", [])
        if isinstance(index, int) or str(index).isdigit()
    }
    instruction_by_preference = {
        int(item.get("preference_index")): str(item.get("instruction", "")).strip()
        for item in response.get("instructions", [])
        if isinstance(item, dict)
        and str(item.get("preference_index", "")).lstrip("-").isdigit()
    }

    kept_entries: list[dict[str, Any]] = []
    if decision == "Keep":
        for match in matches:
            preference_index = int(match["preference_index"])
            if preference_index not in relevant_indexes:
                continue
            instruction = instruction_by_preference.get(preference_index, "").strip()
            if not instruction:
                instruction = (
                    "Use this chunk only when it directly supports the matched user "
                    "preference during response generation."
                )
            kept_entries.append(
                {
                    "chunk_index": chunk["index"],
                    "preference_index": preference_index,
                    "preference": match["preference"],
                    "kind": match["kind"],
                    "instruction": instruction,
                    "rationale": str(response.get("rationale", "")).strip(),
                    "matched_terms": [f"cosine {float(match['score']):.3f}"],
                }
            )

    return {
        "chunk_index": chunk["index"],
        "candidate_matches": matches,
        "kept_entries": kept_entries,
        "rejected_reason": None
        if kept_entries
        else str(response.get("rationale", "LLM discarded this coarse candidate.")).strip(),
    }


def make_coarse_candidate_for_chunk(
    chunk: dict[str, Any],
    preferences: list[dict[str, Any]],
    chunk_vector: np.ndarray,
    preference_vectors: np.ndarray,
    threshold: float,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    scores = np.matmul(preference_vectors, chunk_vector)
    for preference_position, preference in enumerate(preferences):
        score = float(scores[preference_position])
        if score >= threshold:
            matches.append(
                {
                    "preference_index": int(preference["index"]),
                    "preference": preference["preference"],
                    "kind": preference_kind(preference["preference"]),
                    "score": score,
                    "matched_terms": [f"cosine {score:.3f}", f"tau {threshold:.2f}"],
                }
            )
    if not matches:
        return None
    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "chunk_index": int(chunk["index"]),
        "matches": matches,
    }


def make_coarse_candidates(
    chunks: list[dict[str, Any]],
    preferences: list[dict[str, Any]],
    chunk_vectors: np.ndarray,
    preference_vectors: np.ndarray,
    threshold: float,
    emit: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for chunk_position, chunk in enumerate(chunks):
        candidate = make_coarse_candidate_for_chunk(
            chunk,
            preferences,
            chunk_vectors[chunk_position],
            preference_vectors,
            threshold,
        )
        if candidate is not None:
            candidates.append(candidate)
            if emit is not None:
                emit(
                    "coarse_candidate",
                    chunk_index=int(chunk["index"]),
                    processed_chunks=chunk_position + 1,
                    total_chunks=len(chunks),
                    coarse_candidate=candidate,
                )
        elif emit is not None:
            emit(
                "coarse_filtered",
                chunk_index=int(chunk["index"]),
                processed_chunks=chunk_position + 1,
                total_chunks=len(chunks),
            )
    return candidates


def build_instruction_index(
    encoder: ContrieverEncoder,
    evaluations: list[dict[str, Any]],
) -> tuple[int, int, list[str]]:
    instructions = [
        entry["instruction"]
        for evaluation in evaluations
        for entry in evaluation["kept_entries"]
    ]
    if not instructions:
        _, index_bytes = build_index(np.zeros((0, encoder.dimension), dtype="float32"))
        return index_bytes, 0, []
    instruction_vectors = encoder.encode(instructions)
    _, index_bytes = build_index(instruction_vectors)
    return index_bytes, text_bytes(instructions), instructions


def run_pipeline(
    payload: dict[str, Any],
    args: argparse.Namespace,
    encoder: ContrieverEncoder | None = None,
) -> dict[str, Any]:
    threshold = float(payload.get("threshold", 0.3))
    chunks = payload["chunks"]
    preferences = payload["preferences"]
    emit = lambda event, **payload: emit_event(args, event, **payload)

    emit(
        "started",
        total_chunks=len(chunks),
        total_preferences=len(preferences),
        threshold=threshold,
    )

    encoder = encoder or ContrieverEncoder(args.embedding_model)
    chunk_texts = [chunk["text"] for chunk in chunks]
    preference_texts = [preference["preference"] for preference in preferences]
    emit("embedding_started", total_chunks=len(chunks))
    chunk_vectors = encoder.encode(
        chunk_texts,
        on_batch=lambda done, total: emit(
            "embedding_progress",
            processed_chunks=done,
            total_chunks=total,
        ),
    )
    emit("preference_embedding_started", total_preferences=len(preferences))
    preference_vectors = encoder.encode(preference_texts)
    emit("embedding_complete", total_chunks=len(chunks))

    _, existing_index_bytes = build_index(chunk_vectors)
    emit("existing_indexed", existing_faiss_index_bytes=existing_index_bytes)
    emit("coarse_started", total_chunks=len(chunks), threshold=threshold)
    coarse_candidates: list[dict[str, Any]] = []
    fine_evaluations: list[dict[str, Any]] = []
    chunks_by_index = {int(chunk["index"]): chunk for chunk in chunks}

    for chunk_position, chunk in enumerate(chunks):
        processed_chunks = chunk_position + 1
        candidate = make_coarse_candidate_for_chunk(
            chunk,
            preferences,
            chunk_vectors[chunk_position],
            preference_vectors,
            threshold,
        )
        if candidate is None:
            emit(
                "coarse_filtered",
                chunk_index=int(chunk["index"]),
                processed_chunks=processed_chunks,
                total_chunks=len(chunks),
            )
            continue

        coarse_candidates.append(candidate)
        emit(
            "coarse_candidate",
            chunk_index=int(chunk["index"]),
            processed_chunks=processed_chunks,
            total_chunks=len(chunks),
            candidate_count=len(coarse_candidates),
            total_fine=len(coarse_candidates),
            coarse_candidate=candidate,
        )
        emit(
            "fine_chunk_started",
            chunk_index=int(chunk["index"]),
            processed_chunks=processed_chunks,
            total_chunks=len(chunks),
            completed_fine=len(fine_evaluations),
            total_fine=len(coarse_candidates),
        )
        evaluation = evaluate_candidate_with_llm(
            chunks_by_index,
            candidate,
            args.llm_timeout,
            server_url=getattr(args, "llm_server_url", None),
            model=getattr(args, "llm_model", VLLM_MODEL),
        )
        fine_evaluations.append(evaluation)
        emit(
            "fine_chunk_finished",
            chunk_index=int(chunk["index"]),
            processed_chunks=processed_chunks,
            total_chunks=len(chunks),
            completed_fine=len(fine_evaluations),
            total_fine=len(coarse_candidates),
            fine_evaluation=evaluation,
        )

    emit(
        "coarse_complete",
        candidate_count=len(coarse_candidates),
        total_fine=len(coarse_candidates),
    )
    emit(
        "fine_complete",
        completed_fine=len(fine_evaluations),
        total_fine=len(coarse_candidates),
    )

    emit("instruction_index_started")
    epic_index_bytes, instruction_bytes, instructions = build_instruction_index(encoder, fine_evaluations)
    emit("instruction_index_complete", instruction_count=len(instructions))
    kept_chunk_indexes = {
        int(entry["chunk_index"])
        for evaluation in fine_evaluations
        for entry in evaluation["kept_entries"]
    }
    kept_chunks = [chunk for chunk in chunks if int(chunk["index"]) in kept_chunk_indexes]

    return {
        "runtime": {
            "embedding_model": args.embedding_model,
            "embedding_dimension": encoder.dimension,
            "embedding_normalized": True,
            "threshold": threshold,
            "vector_index": "FAISS IndexFlatIP",
            "llm": f"{getattr(args, 'llm_model', VLLM_MODEL)} via vLLM",
            "llm_model_path": getattr(args, "llm_model", VLLM_MODEL),
            "existing_text_bytes": text_bytes(chunk_texts),
            "existing_faiss_index_bytes": existing_index_bytes,
            "existing_total_bytes": text_bytes(chunk_texts) + existing_index_bytes,
            "epic_chunk_text_bytes": text_bytes([chunk["text"] for chunk in kept_chunks]),
            "epic_instruction_bytes": instruction_bytes,
            "epic_faiss_index_bytes": epic_index_bytes,
            "epic_total_bytes": text_bytes([chunk["text"] for chunk in kept_chunks])
            + instruction_bytes
            + epic_index_bytes,
            "instruction_count": len(instructions),
        },
        "coarse_candidates": coarse_candidates,
        "fine_evaluations": fine_evaluations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EPIC indexing with Contriever, FAISS, and vLLM.")
    parser.add_argument("--embedding-model", default=CONTRIEVER_MODEL)
    parser.add_argument("--llm-model", default=VLLM_MODEL)
    parser.add_argument("--llm-timeout", type=int, default=180)
    parser.add_argument("--llm-server-url", default=VLLM_SERVER_URL)
    parser.add_argument("--events", action="store_true")
    args = parser.parse_args()

    try:
        payload = json.load(sys.stdin)
        result = run_pipeline(payload, args)
        if args.events:
            emit_event(args, "complete", result=result)
        else:
            json.dump(result, sys.stdout)
            sys.stdout.write("\n")
        return 0
    except Exception as error:
        if args.events:
            emit_event(
                args,
                "error",
                error=str(error),
                error_type=error.__class__.__name__,
            )
        else:
            json.dump({"error": str(error), "type": error.__class__.__name__}, sys.stdout)
            sys.stdout.write("\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
