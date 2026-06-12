import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CORPUS_DIR = DATA_DIR / "corpus"
CHUNKS_DIR = DATA_DIR / "chunks"
PERSONA_DIR = DATA_DIR / "personas"
INDEX_DIR = DATA_DIR / "indices"
EPIC_INDEX_DIR = INDEX_DIR / "epic"
RAG_INDEX_DIR = INDEX_DIR / "rag"
PROMPT_DIR = BASE_DIR / "prompts"

for d in [CORPUS_DIR, CHUNKS_DIR, PERSONA_DIR, EPIC_INDEX_DIR, RAG_INDEX_DIR, PROMPT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Embedding
EMB_MODEL = "facebook/contriever"
EMB_DIM = 768

# Chunking
CHUNK_SIZE = 200        # tokens (approx words)
CHUNK_OVERLAP = 40
SEMANTIC_THRESHOLD = 0.45  # cosine sim below this → new chunk

# EPIC indexing
COSINE_THRESHOLD = 0.35
TOP_K = 5

# LLM
LLM_BACKEND = os.environ.get("LLM_BACKEND", "claude")  # "claude" | "vllm" | "ollama"
CLAUDE_MODEL = "claude-sonnet-4-5"
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8008/v1")
VLLM_MODEL = os.environ.get("VLLM_MODEL", "Qwen/Qwen3-8B")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-4b-instruct-2507-q4km")

# Reddit (stub — fill in when account is approved)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = "epic-mbti-demo/0.1"

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]
