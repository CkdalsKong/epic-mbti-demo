"""
General corpus collection (shared across all MBTI personas).

Topics: psychology, personality, relationships, career, decision-making,
        lifestyle, self-development — content where MBTI preferences
        naturally lead to different relevance judgments.

Run: python -m src.collect_corpus
Output: data/corpus/corpus.jsonl  (one doc per line)
"""
import os
import sys
import json
import time
import argparse
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CORPUS_DIR

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

# Per-source files: data/corpus/16p.jsonl, psytoday.jsonl, ...
# Merged:           data/corpus/corpus.jsonl  (built by merge_corpus)
def _source_file(source: str) -> Path:
    return CORPUS_DIR / f"{source}.jsonl"

CORPUS_FILE = CORPUS_DIR / "corpus.jsonl"  # merged


def _get_text(soup, selectors: list[str]) -> str:
    for sel in selectors:
        blocks = soup.select(sel)
        if blocks:
            return " ".join(b.get_text(" ", strip=True) for b in blocks)
    return soup.get_text(" ", strip=True)


def _save(source: str, docs: list[dict]):
    out = _source_file(source)
    with open(out, "a", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def _existing_urls(source: str) -> set:
    """Return URLs already collected for this source."""
    f = _source_file(source)
    if not f.exists():
        return set()
    urls = set()
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                urls.add(json.loads(line).get("url", ""))
    return urls


def merge_corpus():
    """Merge all per-source files into corpus.jsonl."""
    all_docs = []
    for src_file in sorted(CORPUS_DIR.glob("*.jsonl")):
        if src_file.name == "corpus.jsonl":
            continue
        with open(src_file, encoding="utf-8") as f:
            docs = [json.loads(l) for l in f if l.strip()]
        all_docs.extend(docs)
        print(f"  {src_file.name}: {len(docs)} docs")
    with open(CORPUS_FILE, "w", encoding="utf-8") as f:
        for d in all_docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"\nMerged → corpus.jsonl: {len(all_docs)} total docs")


# ─── 16personalities blog ─────────────────────────────────────────────────────
# Blog covers relationships, career, stress, growth — rich preference signal

from config import MBTI_TYPES as _MBTI_TYPES

# Type description subpages — static HTML, no JS needed
_16P_TYPE_SECTIONS = [
    "introduction", "strengths-weaknesses", "romantic-relationships",
    "friendships", "parenthood", "career-paths", "workplace-habits",
]
_16P_SLUGS = {
    "INTJ": "intj-architect", "INTP": "intp-logician",
    "ENTJ": "entj-commander", "ENTP": "entp-debater",
    "INFJ": "infj-advocate", "INFP": "infp-mediator",
    "ENFJ": "enfj-protagonist", "ENFP": "enfp-campaigner",
    "ISTJ": "istj-logistician", "ISFJ": "isfj-defender",
    "ESTJ": "estj-executive", "ESFJ": "esfj-consul",
    "ISTP": "istp-virtuoso", "ISFP": "isfp-adventurer",
    "ESTP": "estp-entrepreneur", "ESFP": "esfp-entertainer",
}

def scrape_16p_blog() -> list[dict]:
    """
    16personalities.com is JS-heavy — use two approaches:
    1. HuggingFace 'mbti_big_five' and personality datasets
    2. Direct type description pages (some are static enough)
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [16p] pip install datasets")
        return []

    out_file = _source_file("16p")
    existing_count = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    if existing_count >= 3000:
        print(f"  [16p] already have {existing_count} docs — skipping")
        return []

    docs = []

    # ── HF: Personality / MBTI datasets ───────────────────────────────────
    hf_sources = [
        # (dataset_id, split, text_col, label_col_or_None)
        ("pandalla/MBTI_dataset", "train", "post", "type"),
        ("Sunamro/mbti-dataset", "train", "post", "type"),
        ("username1103/MBTI-dataset", "train", "post", "type"),
    ]
    for ds_id, split, text_col, label_col in hf_sources:
        try:
            print(f"  [16p] trying {ds_id} ...")
            ds = load_dataset(ds_id, split=split)
            count = 0
            for i, item in enumerate(ds):
                text = item.get(text_col, "")
                label = item.get(label_col, "") if label_col else ""
                if len(text) < 60:
                    continue
                docs.append({
                    "source": "16personalities",
                    "topic": label or "mbti_post",
                    "url": f"{ds_id}_{i}",
                    "text": text[:5000],
                })
                count += 1
            print(f"  [16p/{ds_id}] {count} items")
        except Exception as e:
            print(f"  [16p/{ds_id}] {e}")

    # ── Static scrape fallback ─────────────────────────────────────────────
    existing = _existing_urls("16p")
    for mbti, slug in _16P_SLUGS.items():
        for section in _16P_TYPE_SECTIONS[:3]:  # first 3 sections tend to be static
            url = f"https://www.16personalities.com/{slug}-{section}"
            if url in existing:
                continue
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                text = _get_text(soup, ["section p", "article p", "main p"])
                if len(text) > 150:
                    docs.append({"source": "16personalities", "topic": f"{mbti}_{section}", "url": url, "text": text[:5000]})
                    existing.add(url)
                time.sleep(0.8)
            except Exception:
                pass

    if docs:
        _save("16p", docs)
    print(f"  [16p] collected {len(docs)} total docs")
    return []


# ─── Psychology Today ─────────────────────────────────────────────────────────
# Covers personality, emotions, relationships, behavior — high signal

PSYTODAY_TOPICS = [
    "personality", "introversion", "extroversion", "emotional-intelligence",
    "decision-making", "conflict", "relationships", "career",
    "stress", "motivation", "leadership", "communication",
    "empathy", "creativity", "perfectionism", "procrastination",
]

def scrape_psychology_today(max_per_topic: int = 100) -> list[dict]:
    """Paginate through each topic — PT has hundreds of articles per topic."""
    existing = _existing_urls("psytoday")
    docs = []
    for topic in PSYTODAY_TOPICS:
        collected = 0
        page = 0
        while collected < max_per_topic:
            url = (f"https://www.psychologytoday.com/us/basics/{topic}"
                   if page == 0 else
                   f"https://www.psychologytoday.com/us/basics/{topic}?page={page}")
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                links = list({
                    a["href"] for a in soup.select("a[href]")
                    if "/us/blog/" in a.get("href", "") or "/us/articles/" in a.get("href", "")
                })
                if not links:
                    break
                new_links = [l for l in links if l not in existing and
                             ("https://www.psychologytoday.com" + l if not l.startswith("http") else l) not in existing]
                if not new_links:
                    break
                for link in new_links:
                    if collected >= max_per_topic:
                        break
                    full = link if link.startswith("http") else "https://www.psychologytoday.com" + link
                    if full in existing:
                        continue
                    try:
                        r2 = requests.get(full, headers=HEADERS, timeout=15)
                        soup2 = BeautifulSoup(r2.text, "html.parser")
                        text = _get_text(soup2, ["div.field-item p", "article p", ".entry-content p"])
                        if len(text) > 200:
                            docs.append({"source": "psychology_today", "topic": topic, "url": full, "text": text[:8000]})
                            existing.add(full)
                            collected += 1
                        time.sleep(0.8)
                    except Exception as e:
                        print(f"    [psytoday] {full}: {e}")
                page += 1
            except Exception as e:
                print(f"  [psytoday] topic={topic} page={page}: {e}")
                break
        print(f"  [psytoday/{topic}] {collected} articles")
    print(f"  [psytoday] total collected {len(docs)} articles")
    return docs


# ─── Thought Catalog ──────────────────────────────────────────────────────────
# Lifestyle essays — personal voice, strong value/preference signal

TC_TAGS = [
    "personality", "introvert", "extrovert", "relationships",
    "self-improvement", "career", "anxiety", "communication",
    "friendship", "life-lessons", "emotional-intelligence",
]

def scrape_thought_catalog(max_per_tag: int = 50) -> list[dict]:
    """Paginate through TC tag pages — each tag has hundreds of articles."""
    existing = _existing_urls("thoughtcatalog")
    docs = []
    for tag in TC_TAGS:
        collected = 0
        page = 1
        while collected < max_per_tag:
            url = (f"https://thoughtcatalog.com/tag/{tag}/" if page == 1
                   else f"https://thoughtcatalog.com/tag/{tag}/page/{page}/")
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    break
                soup = BeautifulSoup(r.text, "html.parser")
                links = [
                    a["href"] for a in soup.select("h2.entry-title a, h3.entry-title a")
                    if a.get("href") and a["href"] not in existing
                ]
                if not links:
                    break
                for link in links:
                    if collected >= max_per_tag or link in existing:
                        continue
                    try:
                        r2 = requests.get(link, headers=HEADERS, timeout=15)
                        soup2 = BeautifulSoup(r2.text, "html.parser")
                        text = _get_text(soup2, ["div.post-body p", "article p", ".entry-content p"])
                        if len(text) > 200:
                            docs.append({"source": "thought_catalog", "topic": tag, "url": link, "text": text[:8000]})
                            existing.add(link)
                            collected += 1
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"    [tc] {link}: {e}")
                page += 1
            except Exception as e:
                print(f"  [tc] tag={tag} page={page}: {e}")
                break
        print(f"  [tc/{tag}] {collected} articles")
    print(f"  [thoughtcatalog] total collected {len(docs)} articles")
    return docs


# ─── 나무위키 ─────────────────────────────────────────────────────────────────
# MBTI type descriptions + personality theory — background knowledge

NAMU_PAGES = [
    "MBTI", "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
    "내향성과 외향성", "성격유형검사", "인지기능 (MBTI)",
]

def scrape_namuwiki() -> list[dict]:
    """
    namu.wiki is JS-heavy — use Korean Wikipedia via HuggingFace instead.
    Covers MBTI + psychology + personality topics in Korean.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [namuwiki→kowiki] pip install datasets")
        return []

    out_file = _source_file("namuwiki")
    existing_count = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    if existing_count >= 5000:
        print(f"  [kowiki] already have {existing_count} docs — skipping")
        return []

    KO_KEYWORDS = {
        "mbti", "성격", "내향", "외향", "심리", "감정", "관계", "소통",
        "자아", "의사결정", "리더십", "직업", "커리어", "스트레스", "동기",
        "우울", "불안", "공감", "자존감", "친구", "연애", "가치관",
        "인지", "행동", "습관", "자기계발", "행복", "의미",
    }

    print("  [kowiki] streaming Korean Wikipedia (HuggingFace)...")
    try:
        ds = load_dataset(
            "wikimedia/wikipedia", "20231101.ko",
            split="train", streaming=True,
        )
        docs, count = [], 0
        target = 5000 - existing_count
        for article in tqdm(ds, desc="kowiki", total=target):
            if count >= target:
                break
            title = article.get("title", "")
            text = article.get("text", "")
            if len(text) < 200:
                continue
            snippet = (title + " " + text[:300]).lower()
            if not any(kw in snippet for kw in KO_KEYWORDS):
                continue
            docs.append({
                "source": "namuwiki",
                "topic": title,
                "url": f"https://ko.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "text": text[:6000],
            })
            count += 1
            if len(docs) >= 500:
                _save("namuwiki", docs)
                docs = []
        if docs:
            _save("namuwiki", docs)
        print(f"  [kowiki] collected {count} articles")
    except Exception as e:
        print(f"  [kowiki] {e}")
    return []


# ─── Curated MBTI lifestyle seed docs ────────────────────────────────────────
# Small hand-crafted seed ensuring each preference dimension is covered
# even if scrapers partially fail.

SEED_DOCS = [
    {
        "source": "seed", "topic": "introversion_preference",
        "url": "", "text": (
            "Introverted people recharge by spending time alone and prefer deep one-on-one "
            "conversations over large social gatherings. They tend to think carefully before "
            "speaking and may find constant social interaction draining. Introverts often excel "
            "at focused, independent work and deep analytical thinking. They prefer meaningful "
            "connections over a wide social network."
        )
    },
    {
        "source": "seed", "topic": "extroversion_preference",
        "url": "", "text": (
            "Extroverted people gain energy from social interaction and enjoy being part of "
            "groups and teams. They tend to think out loud, process ideas through conversation, "
            "and feel energized by meeting new people. Extroverts often prefer collaborative "
            "environments and are comfortable with spontaneous social plans. They may find "
            "prolonged solitude draining."
        )
    },
    {
        "source": "seed", "topic": "thinking_vs_feeling_decisions",
        "url": "", "text": (
            "People who prefer Thinking in decision-making prioritize logic, objective criteria, "
            "and consistency. They tend to focus on facts and principles rather than personal "
            "impact or interpersonal harmony. In contrast, Feeling-oriented people weigh the "
            "human element heavily — how decisions affect individuals, relationships, and group "
            "cohesion. Neither is more emotional; they simply apply different priorities."
        )
    },
    {
        "source": "seed", "topic": "judging_vs_perceiving_lifestyle",
        "url": "", "text": (
            "Judging types prefer structure, planning, and decisiveness. They feel comfortable "
            "when things are organized and resolved. Perceiving types prefer flexibility, "
            "spontaneity, and keeping options open. They adapt easily to change and may delay "
            "final decisions to gather more information. Both approaches have strengths: "
            "Judging brings reliability, Perceiving brings adaptability."
        )
    },
    {
        "source": "seed", "topic": "intuition_vs_sensing",
        "url": "", "text": (
            "Intuitive personalities focus on patterns, possibilities, and the big picture. "
            "They enjoy abstract thinking, theoretical discussions, and imagining future "
            "scenarios. Sensing personalities focus on concrete facts, present realities, "
            "and practical details. They trust direct experience over theory and prefer "
            "actionable, tangible information over speculation."
        )
    },
    {
        "source": "seed", "topic": "conflict_styles",
        "url": "", "text": (
            "Different personality types approach conflict in fundamentally different ways. "
            "Analytical types prefer to address conflict directly by identifying the logical "
            "root cause and proposing systematic solutions. Empathetic types prioritize "
            "emotional acknowledgment before problem-solving. Assertive types confront issues "
            "quickly to resolve them, while conflict-averse types may avoid direct confrontation "
            "in favor of quiet accommodation or seeking external mediation."
        )
    },
    {
        "source": "seed", "topic": "career_satisfaction",
        "url": "", "text": (
            "Career satisfaction varies significantly by personality type. Analytical, "
            "independent thinkers thrive in roles offering intellectual challenge and autonomy. "
            "People-oriented types find meaning in roles that involve mentoring, counseling, "
            "or community impact. Organized, detail-focused types excel in structured environments "
            "with clear processes. Creative, flexible types prefer open-ended roles where they can "
            "experiment and innovate. Matching career to personality type significantly predicts "
            "long-term job satisfaction and performance."
        )
    },
    {
        "source": "seed", "topic": "relationship_compatibility",
        "url": "", "text": (
            "Relationship compatibility depends less on shared personality type and more on "
            "mutual understanding of differences. Complementary types — such as Thinking and "
            "Feeling — can balance each other when both parties appreciate what the other offers. "
            "Communication style mismatch (e.g., direct vs. indirect, expressive vs. reserved) "
            "is often the primary source of friction. Successful relationships across type "
            "differences require both partners to acknowledge and adapt to each other's "
            "communication and emotional needs."
        )
    },
    {
        "source": "seed", "topic": "stress_and_coping",
        "url": "", "text": (
            "Stress manifests and is managed differently across personality types. Introverts "
            "often need quiet solitude to recover from overwhelming situations, while extroverts "
            "may cope by talking through problems with friends. Thinking types may respond to "
            "stress by over-analyzing, while Feeling types may internalize and personalize "
            "stressors. Structured personalities find relief in regaining control through "
            "planning, while flexible personalities cope by adapting and letting go of rigid "
            "expectations."
        )
    },
    {
        "source": "seed", "topic": "motivation_and_meaning",
        "url": "", "text": (
            "What motivates people varies deeply by personality. Achievement-driven personalities "
            "are motivated by measurable goals, mastery, and external recognition. Meaning-driven "
            "personalities need to feel that their work contributes to something larger than "
            "themselves. Security-oriented types find motivation in stability and dependability. "
            "Experience-seeking types are motivated by novelty, variety, and freedom. "
            "Understanding one's core motivational pattern is key to sustained engagement and "
            "psychological well-being."
        )
    },
]

def get_seed_docs() -> list[dict]:
    existing = _existing_urls("seed")
    # seed docs have empty url — always include (idempotent: overwrite file)
    new_docs = SEED_DOCS if not existing else []
    print(f"  [seed] {len(new_docs)} seed docs")
    return new_docs


# ─── Wikipedia via HuggingFace datasets (streaming) ──────────────────────────
# Streams the full Wikipedia dataset and keeps articles whose title or
# opening text matches personality/psychology/lifestyle keywords.
# No 20GB download — processes in streaming mode, saves matching docs only.

WIKI_KEYWORDS = {
    # Personality & MBTI
    "personality", "introvert", "extrovert", "mbti", "myers-briggs",
    "temperament", "character trait", "cognitive function",
    # Psychology
    "psychology", "emotion", "motivation", "behavior", "mental health",
    "self-esteem", "anxiety", "depression", "attachment", "empathy",
    "emotional intelligence", "mindfulness", "resilience", "trauma",
    # Relationships & social
    "relationship", "friendship", "communication", "conflict", "trust",
    "intimacy", "social anxiety", "loneliness", "belonging",
    # Career & decision
    "career", "leadership", "decision-making", "procrastination",
    "perfectionism", "productivity", "creativity", "ambition",
    # Lifestyle & values
    "lifestyle", "habit", "routine", "self-improvement", "identity",
    "meaning", "purpose", "happiness", "well-being", "fulfillment",
}

def scrape_wikipedia(max_docs: int = 30000) -> list[dict]:
    """
    Stream HuggingFace Wikipedia dataset, filter by keyword relevance.
    Requires: pip install datasets
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [wikipedia] Install datasets: pip install datasets")
        return []

    out_file = _source_file("wikipedia")
    existing_count = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    if existing_count >= max_docs:
        print(f"  [wikipedia] already have {existing_count} docs — skipping")
        return []

    print(f"  [wikipedia] streaming HuggingFace wikipedia dataset (target: {max_docs} docs)...")
    dataset = load_dataset(
        "wikimedia/wikipedia", "20231101.en",
        split="train", streaming=True, trust_remote_code=True,
    )

    saved_count = existing_count
    buf = []
    seen = set()
    pbar = tqdm(total=max_docs, desc="wikipedia")

    for article in dataset:
        if saved_count >= max_docs:
            break
        title = article.get("title", "")
        text = article.get("text", "")
        if not text or len(text) < 200:
            continue
        url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        if url in seen:
            continue

        snippet = (title + " " + text[:500]).lower()
        if not any(kw in snippet for kw in WIKI_KEYWORDS):
            continue

        buf.append({
            "source": "wikipedia",
            "topic": title,
            "url": url,
            "text": text[:8000],
        })
        seen.add(url)
        saved_count += 1
        pbar.update(1)

        if len(buf) >= 1000:
            _save("wikipedia", buf)
            buf = []

    pbar.close()
    if buf:
        _save("wikipedia", buf)

    total = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    print(f"  [wikipedia] collected {total} articles total")
    return []  # already saved incrementally


# ─── Reddit via Arctic Shift API + HuggingFace datasets ──────────────────────
# Arctic Shift: free, no auth, community-maintained Pushshift mirror
# HF datasets: pre-packaged Reddit datasets as fallback

# Personality/lifestyle keywords to filter HF Reddit datasets
_REDDIT_KEYWORDS = {
    "mbti", "introvert", "extrovert", "personality", "infp", "intj", "infj",
    "intp", "enfp", "enfj", "entj", "entp", "isfp", "isfj", "istj", "istp",
    "esfp", "esfj", "estj", "estp", "relationship", "social anxiety",
    "self-improvement", "career", "emotion", "conflict", "communication",
    "motivation", "identity", "purpose", "meaning", "stress", "decision",
    "friendship", "loneliness", "introversion", "empathy", "attachment",
}

def download_reddit_hf(max_docs: int = 50000) -> list[dict]:
    """
    Load Reddit data from HuggingFace datasets (no API, no auth needed).

    Sources tried in order:
    1. sentence-transformers/reddit-title-body  (~800k posts, personality-rich)
    2. reddit_tifu ("long" split, ~42k real Reddit posts)
    3. Amod/mental_health_counseling_conversations (advice/emotion content)
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [reddit-hf] pip install datasets")
        return []

    out_file = _source_file("reddit")
    existing_count = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    if existing_count >= max_docs:
        print(f"  [reddit-hf] already have {existing_count} docs — skipping")
        return []

    remaining = max_docs - existing_count
    existing_urls = _existing_urls("reddit")
    total_added = 0

    # ── Source 1: sentence-transformers/reddit-title-body ──────────────────
    # 800k+ Reddit posts across many subreddits. Parquet format, no script.
    if total_added < remaining:
        try:
            print("  [reddit-hf] loading sentence-transformers/reddit-title-body ...")
            ds = load_dataset(
                "sentence-transformers/reddit-title-body",
                split="train", streaming=True,
            )
            docs, count = [], 0
            for item in tqdm(ds, desc="reddit-title-body", total=remaining):
                if total_added + count >= remaining:
                    break
                title = item.get("title", "")
                body = item.get("body", "")
                url = f"reddit_tb_{item.get('id', count)}"
                if url in existing_urls:
                    continue
                full_text = f"{title}\n\n{body}".strip()
                text_lower = full_text[:300].lower()
                if len(full_text) < 80:
                    continue
                if not any(kw in text_lower for kw in _REDDIT_KEYWORDS):
                    continue
                docs.append({"source": "reddit", "topic": "lifestyle", "url": url, "text": full_text[:5000]})
                existing_urls.add(url)
                count += 1
                if len(docs) >= 2000:
                    _save("reddit", docs)
                    docs = []
            if docs:
                _save("reddit", docs)
            total_added += count
            print(f"  [reddit-hf/title-body] added {count}")
        except Exception as e:
            print(f"  [reddit-hf/title-body] {e}")

    # ── Source 2: reddit_tifu ──────────────────────────────────────────────
    # ~42k long Reddit posts (personal stories, lifestyle, advice)
    if total_added < remaining:
        try:
            print("  [reddit-hf] loading reddit_tifu ...")
            ds = load_dataset("reddit_tifu", "long", split="train", streaming=True)
            docs, count = [], 0
            for item in tqdm(ds, desc="reddit_tifu"):
                if total_added + count >= remaining:
                    break
                title = item.get("title", "")
                body = item.get("documents", "")
                url = f"tifu_{item.get('ups', count)}_{count}"
                if url in existing_urls:
                    continue
                full_text = f"{title}\n\n{body}".strip()
                if len(full_text) < 80:
                    continue
                docs.append({"source": "reddit", "topic": "tifu_lifestyle", "url": url, "text": full_text[:5000]})
                existing_urls.add(url)
                count += 1
                if len(docs) >= 2000:
                    _save("reddit", docs)
                    docs = []
            if docs:
                _save("reddit", docs)
            total_added += count
            print(f"  [reddit-hf/tifu] added {count}")
        except Exception as e:
            print(f"  [reddit-hf/tifu] {e}")

    # ── Source 3: Amod/mental_health_counseling_conversations ──────────────
    # ~3k emotional support / advice conversations — high personality signal
    if total_added < remaining:
        try:
            print("  [reddit-hf] loading mental health counseling dataset ...")
            ds = load_dataset("Amod/mental_health_counseling_conversations", split="train")
            docs, count = [], 0
            for i, item in enumerate(ds):
                if total_added + count >= remaining:
                    break
                context = item.get("Context", "")
                response = item.get("Response", "")
                full_text = f"{context}\n\n{response}".strip()
                if len(full_text) < 80:
                    continue
                url = f"mhcc_{i}"
                docs.append({"source": "reddit", "topic": "mental_health_advice", "url": url, "text": full_text[:5000]})
                count += 1
            if docs:
                _save("reddit", docs)
            total_added += count
            print(f"  [reddit-hf/mhcc] added {count}")
        except Exception as e:
            print(f"  [reddit-hf/mhcc] {e}")

    total = sum(1 for _ in open(out_file) if _.strip()) if out_file.exists() else 0
    print(f"  [reddit-hf] total {total} docs saved")
    return []


# ─── Reddit stub ──────────────────────────────────────────────────────────────

def scrape_reddit(limit: int = 200) -> list[dict]:
    try:
        import praw
        from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
        if not REDDIT_CLIENT_ID:
            print("  [reddit] No credentials — skipping")
            return []
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        existing = _existing_urls("reddit")
        docs = []
        subreddits = ["mbti", "intj", "infp", "enfp", "intp", "personality"]
        for sub_name in subreddits:
            sub = reddit.subreddit(sub_name)
            for post in sub.top(time_filter="year", limit=limit // len(subreddits)):
                url = f"https://reddit.com{post.permalink}"
                if url in existing or not post.selftext or len(post.selftext) < 100:
                    continue
                docs.append({
                    "source": "reddit",
                    "topic": sub_name,
                    "url": url,
                    "text": f"{post.title}\n\n{post.selftext}"[:5000],
                })
        print(f"  [reddit] collected {len(docs)} posts")
        return docs
    except Exception as e:
        print(f"  [reddit] {e}")
        return []


# ─── Orchestrator ─────────────────────────────────────────────────────────────

SOURCE_FNS = {
    "16p":            scrape_16p_blog,
    "psytoday":       scrape_psychology_today,
    "thoughtcatalog": scrape_thought_catalog,
    "namuwiki":       scrape_namuwiki,
    "wikipedia":      scrape_wikipedia,          # HuggingFace streaming, ~30k docs
    "reddit":         download_reddit_hf,       # HuggingFace Reddit datasets, ~50k docs
    "seed":           get_seed_docs,
}

def collect(sources: list[str], parallel: bool = True):
    CORPUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    total_before = sum(1 for _ in open(CORPUS_FILE) if _.strip()) if CORPUS_FILE.exists() else 0
    print(f"Existing corpus: {total_before} docs")
    print(f"Sources: {sources}  |  parallel={parallel}\n")

    def run_source(src):
        fn = SOURCE_FNS.get(src)
        if not fn:
            print(f"[{src}] unknown source — skipping")
            return
        print(f"[{src}] starting...")
        try:
            docs = fn()
        except Exception as e:
            print(f"[{src}] ERROR: {e}")
            docs = []
        # Some sources (wikipedia, reddit, namuwiki) save incrementally and return []
        out = _source_file(src)
        count = sum(1 for _ in open(out) if _.strip()) if out.exists() else 0
        if docs:
            _save(src, docs)
            count += len(docs)
        print(f"[{src}] ✅ {count} docs in {src}.jsonl")

    if parallel:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        # Each source hits different domains — safe to parallelize
        with ThreadPoolExecutor(max_workers=len(sources)) as ex:
            futures = {ex.submit(run_source, src): src for src in sources}
            for fut in as_completed(futures):
                fut.result()  # surface exceptions
    else:
        for src in sources:
            run_source(src)

    print("\nMerging all source files → corpus.jsonl ...")
    merge_corpus()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="seed,16p,psytoday,thoughtcatalog,namuwiki")
    args = parser.parse_args()
    collect(args.sources.split(","))
