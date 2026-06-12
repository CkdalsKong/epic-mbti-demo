"""
EPIC MBTI Demo — Streamlit UI
Run: streamlit run app.py
"""
import sys
import json
import time
import streamlit as st
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import MBTI_TYPES, PERSONA_DIR

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EPIC · MBTI Demo",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Persona metadata ─────────────────────────────────────────────────────────

@st.cache_resource
def load_persona_meta():
    with open(PERSONA_DIR / "mbti_preferences.json") as f:
        return json.load(f)

PERSONA_META = load_persona_meta()

# MBTI group styling
GROUPS = {
    "Analysts"  : {"types": ["INTJ","INTP","ENTJ","ENTP"], "color": "#4a90d9", "bg": "#0d1f35", "emoji": "🔵"},
    "Diplomats" : {"types": ["INFJ","INFP","ENFJ","ENFP"], "color": "#4caf82", "bg": "#0d2b1e", "emoji": "🟢"},
    "Sentinels" : {"types": ["ISTJ","ISFJ","ESTJ","ESFJ"], "color": "#e8a838", "bg": "#2b1f0a", "emoji": "🟡"},
    "Explorers" : {"types": ["ISTP","ISFP","ESTP","ESFP"], "color": "#e85555", "bg": "#2b0d0d", "emoji": "🔴"},
}

TYPE_TO_GROUP = {t: g for g, v in GROUPS.items() for t in v["types"]}
TYPE_COLOR    = {t: GROUPS[g]["color"] for t, g in TYPE_TO_GROUP.items()}
TYPE_BG       = {t: GROUPS[g]["bg"]    for t, g in TYPE_TO_GROUP.items()}

EXAMPLE_QS = [
    "How do I handle conflict with a coworker?",
    "What's the best way to make a big life decision?",
    "How do I deal with feeling overwhelmed at work?",
    "What makes a relationship feel truly fulfilling?",
    "How do I stay motivated when things get hard?",
    "How do I make new friends as an adult?",
]

# ─── CSS ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.2rem 2rem 2rem; max-width: 1440px; }

/* ── Header ── */
.epic-header {
    background: linear-gradient(135deg, #0d1117 0%, #0d1f35 60%, #0f3460 100%);
    border: 1px solid #1e3a5f;
    border-radius: 20px;
    padding: 1.6rem 2.4rem;
    margin-bottom: 1.4rem;
    display: flex; align-items: center; justify-content: space-between;
}
.epic-logo { font-size: 1.9rem; font-weight: 800; color: #fff; letter-spacing: -1px; }
.epic-logo span { color: #4a90d9; }
.epic-tagline { font-size: 0.82rem; color: #5a8ab0; margin-top: 2px; }
.epic-badge {
    background: #0d2040; border: 1px solid #2d5080;
    border-radius: 10px; padding: 6px 14px;
    font-size: 0.78rem; color: #6aaad4; font-weight: 600;
}

/* ── MBTI grid ── */
.mbti-section-label {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 1px;
    color: #3a4a5a; text-transform: uppercase; margin-bottom: 4px;
}
div[data-testid="column"] button {
    border-radius: 10px !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    padding: 6px 4px !important;
    transition: all 0.15s !important;
}

/* ── Selected persona banner ── */
.persona-banner {
    border-radius: 14px; padding: 1rem 1.4rem;
    margin: 0.8rem 0; display: flex; align-items: center; gap: 16px;
}
.persona-mbti { font-size: 2rem; font-weight: 800; }
.persona-label { font-size: 0.9rem; font-weight: 600; opacity: 0.8; }
.persona-desc { font-size: 0.8rem; opacity: 0.65; margin-top: 2px; }
.pref-tag {
    display: inline-block; border-radius: 6px;
    padding: 3px 9px; margin: 2px;
    font-size: 0.72rem; font-weight: 500;
}

/* ── Example questions ── */
.eq-btn {
    background: #111824; border: 1px solid #1e2c3a;
    border-radius: 8px; padding: 7px 12px;
    font-size: 0.78rem; color: #6a8aaa; cursor: pointer;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── Method cards ── */
.method-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 10px; padding-bottom: 10px;
    border-bottom: 1px solid #1e2836;
}
.method-dot {
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0;
}
.method-name { font-size: 1rem; font-weight: 700; }
.method-sub  { font-size: 0.72rem; color: #4a6a8a; margin-top: 1px; }

/* ── Metric chips ── */
.metric-row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.mchip {
    background: #0d1420; border: 1px solid #1a2535;
    border-radius: 8px; padding: 5px 12px; font-size: 0.76rem;
}
.mchip-label { color: #3a5a7a; font-size: 0.68rem; display: block; }
.mchip-value { color: #a0c8e8; font-weight: 700; }

/* ── Response box ── */
.response-box {
    background: #080d14; border: 1px solid #1a2535;
    border-radius: 12px; padding: 1.1rem 1.3rem;
    font-size: 0.88rem; line-height: 1.7;
    color: #c5d8ea; min-height: 180px;
}
.response-placeholder {
    color: #2a3a4a; font-style: italic; font-size: 0.85rem;
}

/* ── Preference match badge ── */
.pref-match {
    background: #0a1e10; border: 1px solid #1a3a20;
    border-radius: 8px; padding: 6px 12px;
    font-size: 0.75rem; color: #4caf82;
    margin-bottom: 10px; display: flex; align-items: center; gap: 6px;
}

/* ── Retrieved doc cards ── */
.doc-card {
    background: #080d14; border: 1px solid #141e2a;
    border-radius: 8px; padding: 8px 12px; margin-top: 6px;
}
.doc-card-source { font-size: 0.68rem; color: #3a6a9a; font-weight: 600; margin-bottom: 3px; }
.doc-card-inst   { font-size: 0.72rem; color: #3a8a5a; font-style: italic; margin-bottom: 4px; }
.doc-card-text   { font-size: 0.76rem; color: #5a7a9a; line-height: 1.5; }

/* ── Stats bar ── */
.stats-bar {
    background: #080d14; border: 1px solid #141e2a;
    border-radius: 12px; padding: 0.8rem 1.4rem;
    display: flex; gap: 32px; align-items: center;
    margin: 0.8rem 0;
}
.stat-item { text-align: center; }
.stat-value { font-size: 1.3rem; font-weight: 800; color: #4a90d9; }
.stat-label { font-size: 0.68rem; color: #3a5a7a; text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Divider ── */
.section-divider {
    border: none; border-top: 1px solid #141e2a; margin: 1rem 0;
}

/* ── Comparison delta ── */
.delta-better { color: #4caf82; font-weight: 700; }
.delta-worse  { color: #e85555; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ────────────────────────────────────────────────────────────

for k, v in [
    ("mbti", "INTJ"),
    ("query", ""),
    ("result", None),
    ("backend", "claude"),
    ("show_prefs", False),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown("""
<div class="epic-header">
  <div>
    <div class="epic-logo"><span>EPIC</span> · MBTI Personalization Demo</div>
    <div class="epic-tagline">
      Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp;
      Same question, different answers for different personalities
    </div>
  </div>
  <div style="display:flex;gap:8px">
    <div class="epic-badge">📄 ACL 2025 Findings</div>
    <div class="epic-badge">🔵 EPIC vs ⚪ Plain RAG</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Top controls row ─────────────────────────────────────────────────────────

col_mbti, col_backend = st.columns([5, 1])

with col_backend:
    st.markdown("**LLM**")
    backend = st.radio(
        "backend", ["claude", "vllm", "ollama"],
        index=["claude","vllm","ollama"].index(st.session_state.backend),
        label_visibility="collapsed",
    )
    st.session_state.backend = backend

with col_mbti:
    st.markdown("**Choose your MBTI persona**")
    for group_name, ginfo in GROUPS.items():
        gcols = st.columns([1.2] + [1]*4)
        g_color = ginfo["color"]
        g_emoji = ginfo["emoji"]
        gcols[0].markdown(
            f"<div style='padding-top:6px'>"
            f"<span style='color:{g_color};font-weight:700;font-size:0.72rem'>"
            f"{g_emoji} {group_name}</span></div>",
            unsafe_allow_html=True,
        )
        for col, t in zip(gcols[1:], ginfo["types"]):
            is_sel = (t == st.session_state.mbti)
            t_label = PERSONA_META[t]["label"]
            label = f"**{t}**\n{t_label}"
            if col.button(
                label, key=f"mbti_{t}",
                type="primary" if is_sel else "secondary",
                use_container_width=True,
            ):
                st.session_state.mbti = t
                st.session_state.result = None
                st.rerun()

# ─── Persona banner ───────────────────────────────────────────────────────────

mbti  = st.session_state.mbti
meta  = PERSONA_META[mbti]
color = TYPE_COLOR[mbti]
bg    = TYPE_BG[mbti]

st.markdown(
    f'<div class="persona-banner" style="background:{bg};border:1px solid {color}33">'
    f'  <div class="persona-mbti" style="color:{color}">{mbti}</div>'
    f'  <div>'
    f'    <div class="persona-label" style="color:{color}">{meta["label"]}</div>'
    f'    <div class="persona-desc" style="color:#8a9ab0">{meta["description"]}</div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)

with st.expander("📋 Preferences used for EPIC indexing", expanded=False):
    tags = "".join(
        f'<span class="pref-tag" style="background:{bg};border:1px solid {color}44;color:{color}cc">'
        f'• {p}</span>'
        for p in meta["preferences"]
    )
    st.markdown(f'<div style="line-height:2.2">{tags}</div>', unsafe_allow_html=True)

# ─── Index stats bar ──────────────────────────────────────────────────────────

try:
    from src.retriever import get_index_stats
    stats = get_index_stats(mbti)
    epic_n  = stats.get("epic_indexed_chunks", "—")
    total_n = stats.get("epic_total_input", "—")
    rag_n   = stats.get("rag_total_chunks", "—")
    cosine_n = stats.get("epic_after_cosine", "—")

    if isinstance(total_n, int) and isinstance(epic_n, int) and total_n > 0:
        compress = f"{epic_n/total_n*100:.1f}%"
    else:
        compress = "—"

    st.markdown(
        f'<div class="stats-bar">'
        f'  <div class="stat-item"><div class="stat-value" style="color:{color}">{epic_n:,}</div><div class="stat-label">EPIC Index Size</div></div>'
        f'  <div style="color:#1a2535">│</div>'
        f'  <div class="stat-item"><div class="stat-value" style="color:#3a5a7a">{total_n:,}</div><div class="stat-label">Total Chunks</div></div>'
        f'  <div style="color:#1a2535">│</div>'
        f'  <div class="stat-item"><div class="stat-value" style="color:#4caf82">{compress}</div><div class="stat-label">Compression</div></div>'
        f'  <div style="color:#1a2535">│</div>'
        f'  <div class="stat-item"><div class="stat-value" style="color:#e8a838">{rag_n:,}</div><div class="stat-label">RAG Index Size</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
except Exception:
    st.info("Index not built yet — run `python run_pipeline.py --steps index_epic,index_rag` first")

# ─── Query input ──────────────────────────────────────────────────────────────

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
st.markdown("**Try a question** — or pick one below")

eq_cols = st.columns(len(EXAMPLE_QS))
for col, q in zip(eq_cols, EXAMPLE_QS):
    if col.button(q[:35] + "…", key=f"eq_{q[:15]}", use_container_width=True):
        st.session_state.query = q
        st.rerun()

query = st.text_input(
    "question", value=st.session_state.query,
    placeholder="Ask anything — relationships, career, decisions, stress...",
    label_visibility="collapsed",
)
st.session_state.query = query

run = st.button(
    "⚡ Generate Personalized Response",
    type="primary",
    disabled=not query.strip(),
    use_container_width=True,
)

# ─── Run ──────────────────────────────────────────────────────────────────────

if run and query.strip():
    from src.retriever import epic_retrieve, rag_retrieve
    from src.generator import generate_epic, generate_rag

    with st.spinner("Retrieving and generating..."):
        epic_r = epic_retrieve(query, mbti)
        rag_r  = rag_retrieve(query)

        t0 = time.perf_counter()
        epic_resp = (
            generate_epic(query, mbti, meta, epic_r["docs"], backend=backend)
            if epic_r.get("docs")
            else f"⚠️ EPIC index for {mbti} not found. Run indexing first."
        )
        epic_gen_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        rag_resp = (
            generate_rag(query, rag_r["docs"], backend=backend)
            if rag_r.get("docs")
            else "⚠️ RAG index not found. Run indexing first."
        )
        rag_gen_ms = (time.perf_counter() - t0) * 1000

    st.session_state.result = {
        "query": query, "mbti": mbti,
        "epic": {
            "response": epic_resp,
            "docs": epic_r.get("docs", []),
            "retr_ms": epic_r.get("latency_ms", 0),
            "gen_ms": round(epic_gen_ms, 1),
            "top_pref": epic_r.get("top_preference", ""),
        },
        "rag": {
            "response": rag_resp,
            "docs": rag_r.get("docs", []),
            "retr_ms": rag_r.get("latency_ms", 0),
            "gen_ms": round(rag_gen_ms, 1),
        },
    }

# ─── Results ──────────────────────────────────────────────────────────────────

if st.session_state.result:
    res  = st.session_state.result
    er   = res["epic"]
    rr   = res["rag"]

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:0.78rem;color:#3a5a7a;margin-bottom:8px">'
        f'Results for &nbsp;<b style="color:{color}">{res["mbti"]}</b>&nbsp; · &nbsp;'
        f'"<i>{res["query"]}</i>"'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_e, col_r = st.columns(2)

    # ── EPIC ──────────────────────────────────────────────────────────────────
    with col_e:
        st.markdown(
            f'<div class="method-header">'
            f'  <div class="method-dot" style="background:{color}"></div>'
            f'  <div>'
            f'    <div class="method-name" style="color:{color}">EPIC (Ours)</div>'
            f'    <div class="method-sub">Persona-aware indexing · preference-augmented retrieval</div>'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Metrics
        st.markdown(
            f'<div class="metric-row">'
            f'  <div class="mchip"><span class="mchip-label">Retrieval</span>'
            f'    <span class="mchip-value">{er["retr_ms"]} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Generation</span>'
            f'    <span class="mchip-value">{er["gen_ms"]} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Docs used</span>'
            f'    <span class="mchip-value">{len(er["docs"])}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Matched preference
        if er.get("top_pref"):
            tp = er["top_pref"]
            short = (tp[:80] + "…") if len(tp) > 80 else tp
            st.markdown(
                f'<div class="pref-match">🎯 Matched preference: {short}</div>',
                unsafe_allow_html=True,
            )

        # Response
        resp_html = er["response"].replace("\n", "<br>")
        st.markdown(
            f'<div class="response-box">{resp_html}</div>',
            unsafe_allow_html=True,
        )

        # Retrieved docs
        if er["docs"]:
            with st.expander(f"📂 Retrieved docs ({len(er['docs'])})", expanded=False):
                for i, doc in enumerate(er["docs"], 1):
                    src  = doc.get("source", "")
                    inst = doc.get("instruction", "")
                    sc   = doc.get("score", 0)
                    txt  = doc.get("text", "")[:220]
                    st.markdown(
                        f'<div class="doc-card">'
                        f'  <div class="doc-card-source">#{i} · {src} · score {sc:.3f}</div>'
                        + (f'  <div class="doc-card-inst">📌 {inst}</div>' if inst else '')
                        + f'  <div class="doc-card-text">{txt}…</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── Plain RAG ─────────────────────────────────────────────────────────────
    with col_r:
        st.markdown(
            '<div class="method-header">'
            '  <div class="method-dot" style="background:#3a4a5a"></div>'
            '  <div>'
            '    <div class="method-name" style="color:#6a8aaa">Plain RAG (Baseline)</div>'
            '    <div class="method-sub">No persona · vanilla retrieval · generic response</div>'
            '  </div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="metric-row">'
            f'  <div class="mchip"><span class="mchip-label">Retrieval</span>'
            f'    <span class="mchip-value">{rr["retr_ms"]} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Generation</span>'
            f'    <span class="mchip-value">{rr["gen_ms"]} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Docs used</span>'
            f'    <span class="mchip-value">{len(rr["docs"])}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Spacer to align with EPIC's preference match badge
        st.markdown('<div style="height:32px"></div>', unsafe_allow_html=True)

        resp_html = rr["response"].replace("\n", "<br>")
        st.markdown(
            f'<div class="response-box" style="border-color:#141e2a">{resp_html}</div>',
            unsafe_allow_html=True,
        )

        if rr["docs"]:
            with st.expander(f"📂 Retrieved docs ({len(rr['docs'])})", expanded=False):
                for i, doc in enumerate(rr["docs"], 1):
                    src = doc.get("source", "")
                    sc  = doc.get("score", 0)
                    txt = doc.get("text", "")[:220]
                    st.markdown(
                        f'<div class="doc-card">'
                        f'  <div class="doc-card-source">#{i} · {src} · score {sc:.3f}</div>'
                        f'  <div class="doc-card-text">{txt}…</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── Comparison summary ────────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    retr_diff = er["retr_ms"] - rr["retr_ms"]
    gen_diff  = er["gen_ms"]  - rr["gen_ms"]

    c1.metric("EPIC Retrieval", f"{er['retr_ms']} ms",
              f"{retr_diff:+.1f} ms vs RAG", delta_color="inverse")
    c2.metric("RAG Retrieval",  f"{rr['retr_ms']} ms")
    c3.metric("EPIC Generation", f"{er['gen_ms']} ms",
              f"{gen_diff:+.1f} ms vs RAG", delta_color="off")
    c4.metric("Total (EPIC)",
              f"{er['retr_ms'] + er['gen_ms']:.0f} ms",
              delta_color="off")

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;padding:1.5rem 0 0.5rem;color:#1e2c3a;font-size:0.72rem">
  EPIC · Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp; ACL 2025 Findings
</div>
""", unsafe_allow_html=True)
