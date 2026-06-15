"""
EPIC MBTI Demo — Streamlit UI (single-page, no-scroll)
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
]

# ─── CSS ──────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; box-sizing: border-box; }
#MainMenu, footer, header { visibility: hidden; }

/* ── Layout ── */
.block-container {
    padding: 0.55rem 1.5rem 1.5rem !important;
    max-width: 100% !important;
}

/* ── Header ── */
.epic-header {
    background: linear-gradient(135deg, #0d1117 0%, #0d1f35 60%, #0f3460 100%);
    border: 1px solid #1e3a5f; border-radius: 12px;
    padding: 0.6rem 1.4rem; margin-bottom: 0.5rem;
    display: flex; align-items: center; justify-content: space-between;
}
.epic-logo { font-size: 1.25rem; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
.epic-logo span { color: #4a90d9; }
.epic-tagline { font-size: 0.68rem; color: #5a8ab0; margin-top: 1px; }
.epic-badge {
    background: #0d2040; border: 1px solid #2d5080;
    border-radius: 6px; padding: 3px 10px;
    font-size: 0.7rem; color: #6aaad4; font-weight: 600;
}

/* ── MBTI grid buttons ── */
div[data-testid="column"] button {
    border-radius: 7px !important; font-size: 0.72rem !important;
    font-weight: 700 !important; padding: 3px 2px !important;
    line-height: 1.3 !important; min-height: 0 !important;
}

/* ── Stats cards ── */
.stat-card {
    background: #060b12; border-radius: 9px;
    padding: 7px 12px;
}

/* ── Method panel header ── */
.method-header {
    display: flex; align-items: center; gap: 8px;
    padding-bottom: 6px; border-bottom: 1px solid #1e2836;
    margin-bottom: 6px;
}
.method-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.method-name { font-size: 0.9rem; font-weight: 700; }
.method-sub  { font-size: 0.62rem; color: #4a6a8a; }

/* ── Metric chips ── */
.mchip {
    background: #0d1420; border: 1px solid #1a2535;
    border-radius: 6px; padding: 2px 8px; font-size: 0.68rem;
    display: inline-block; margin: 1px;
}
.mchip-label { color: #3a5a7a; font-size: 0.58rem; display: block; }
.mchip-value { color: #a0c8e8; font-weight: 700; }

/* ── Response box — fixed height, scrollable ── */
.response-box {
    background: #060b12; border: 1px solid #1a2535;
    border-radius: 9px; padding: 0.75rem 1rem;
    font-size: 0.83rem; line-height: 1.7; color: #c5d8ea;
    height: 220px; overflow-y: auto;
}
.response-box::-webkit-scrollbar { width: 4px; }
.response-box::-webkit-scrollbar-track { background: #0d1420; }
.response-box::-webkit-scrollbar-thumb { background: #1a3a5a; border-radius: 2px; }
.response-placeholder { color: #2a3a4a; font-style: italic; font-size: 0.8rem; }

/* ── Preference match badge ── */
.pref-match {
    background: #0a1e10; border: 1px solid #1a3a20;
    border-radius: 6px; padding: 3px 8px;
    font-size: 0.68rem; color: #4caf82; margin-bottom: 5px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── Fade-in animations ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
}
.resp-animate { animation: fadeUp 0.35s ease-out; }
.eval-animate { animation: fadeUp 0.45s ease-out 0.2s backwards; }

/* ── Eval badges section ── */
.eval-section {
    margin-top: 6px; padding: 6px 8px;
    background: #060b12; border: 1px solid #111e2a;
    border-radius: 7px;
}
.eval-title { font-size: 0.57rem; color: #3a5a7a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }

hr.divider { border: none; border-top: 1px solid #111e2a; margin: 0.4rem 0; }

/* ── Doc cards ── */
.doc-card {
    background: #060b12; border: 1px solid #111e2a;
    border-radius: 6px; padding: 5px 8px; margin-top: 4px;
}
.doc-src  { font-size: 0.62rem; color: #3a6a9a; font-weight: 600; margin-bottom: 1px; }
.doc-inst { font-size: 0.66rem; color: #3a8a5a; font-style: italic; margin-bottom: 2px; }
.doc-txt  { font-size: 0.68rem; color: #4a6a8a; line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ─────────────────────────────────────────────────────────────

for k, v in [("mbti","INTJ"), ("query",""), ("result",None), ("backend","vllm")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Header ───────────────────────────────────────────────────────────────────

st.markdown("""
<div class="epic-header">
  <div>
    <div class="epic-logo"><span>EPIC</span> · MBTI Personalization Demo</div>
    <div class="epic-tagline">Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp; Same question, different answers for different personalities</div>
  </div>
  <div style="display:flex;gap:6px;align-items:center">
    <div class="epic-badge">🏆 ICML 2026</div>
    <div class="epic-badge">⚡ EPIC &nbsp;vs&nbsp; Plain RAG</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Top row: MBTI grid (left) + persona info & stats (right) ─────────────────

left_col, right_col = st.columns([3, 2], gap="medium")

with left_col:
    # Backend selector (tiny, inline)
    bc1, bc2 = st.columns([3, 1])
    bc1.markdown('<div style="font-size:0.75rem;font-weight:700;color:#4a6a8a;margin-bottom:2px">CHOOSE PERSONA</div>', unsafe_allow_html=True)
    with bc2:
        backend = st.selectbox("backend", ["vllm", "claude", "ollama"],
                               index=["vllm","claude","ollama"].index(st.session_state.backend),
                               label_visibility="collapsed")
        st.session_state.backend = backend

    for group_name, ginfo in GROUPS.items():
        gcols = st.columns([1] + [1]*4)
        g_color = ginfo["color"]
        g_emoji = ginfo["emoji"]
        gcols[0].markdown(
            f"<div style='padding-top:4px;font-size:0.65rem;color:{g_color};font-weight:700'>"
            f"{g_emoji} {group_name}</div>",
            unsafe_allow_html=True,
        )
        for col, t in zip(gcols[1:], ginfo["types"]):
            is_sel = (t == st.session_state.mbti)
            t_label = PERSONA_META[t]["label"]
            if col.button(f"**{t}**", key=f"mbti_{t}",
                          type="primary" if is_sel else "secondary",
                          use_container_width=True):
                st.session_state.mbti = t
                st.session_state.result = None
                st.rerun()

with right_col:
    mbti  = st.session_state.mbti
    meta  = PERSONA_META[mbti]
    color = TYPE_COLOR[mbti]
    bg    = TYPE_BG[mbti]

    # Persona banner (compact)
    st.markdown(
        f'<div style="background:{bg};border:1px solid {color}33;border-radius:10px;'
        f'padding:8px 14px;margin-bottom:6px;display:flex;align-items:center;gap:12px">'
        f'  <div style="font-size:1.6rem;font-weight:800;color:{color}">{mbti}</div>'
        f'  <div>'
        f'    <div style="font-size:0.9rem;font-weight:700;color:{color}">{meta["label"]}</div>'
        f'    <div style="font-size:0.68rem;color:#8a9ab0">{meta["description"]}</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Preferences (collapsible)
    tags = "".join(
        f'<span style="display:inline-block;border-radius:5px;padding:2px 8px;margin:2px;'
        f'background:{bg};border:1px solid {color}44;color:{color}cc;font-size:0.65rem">• {p}</span>'
        for p in meta["preferences"]
    )
    st.markdown(
        f'<details style="margin-bottom:6px">'
        f'<summary style="font-size:0.68rem;color:{color};cursor:pointer;user-select:none;margin-bottom:4px">'
        f'📋 Preferences used for EPIC indexing</summary>'
        f'<div style="line-height:2;margin-top:4px">{tags}</div>'
        f'</details>',
        unsafe_allow_html=True,
    )

    # Index stats — always visible, compact two-card layout
    try:
        from src.retriever import get_index_stats
        stats   = get_index_stats(mbti)
        epic_n  = stats.get("epic_indexed_chunks", 0)
        rag_n   = stats.get("rag_total_chunks", 0)
        epic_mb = stats.get("epic_total_mb", 0)
        rag_mb  = stats.get("rag_index_mb", 0)
        chunk_ratio = round(rag_n / epic_n) if epic_n else 0
        mb_ratio    = round(rag_mb / epic_mb) if epic_mb else 0
        epic_bar_w  = f"{max(2, round(epic_n / rag_n * 100))}%" if rag_n else "2%"
        epic_mb_w   = f"{max(2, round(epic_mb / rag_mb * 100))}%" if rag_mb else "2%"

        def _mini_card(title, tc, chunks_v, index_v, bar_cw, bar_mw, bc):
            return (
                f'<div style="flex:1;background:#060b12;border:1px solid {tc}28;border-radius:8px;padding:8px 12px">'
                f'  <div style="font-size:0.6rem;font-weight:800;color:{tc};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">{title}</div>'
                f'  <div style="margin-bottom:5px">'
                f'    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px">'
                f'      <span style="font-size:0.55rem;color:#3a5a7a;text-transform:uppercase">Chunks</span>'
                f'      <span style="font-size:0.95rem;font-weight:800;color:{tc}">{chunks_v}</span>'
                f'    </div>'
                f'    <div style="background:#0d1420;border-radius:2px;height:4px;overflow:hidden">'
                f'      <div style="width:{bar_cw};background:{bc};height:100%;border-radius:2px"></div>'
                f'    </div>'
                f'  </div>'
                f'  <div>'
                f'    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:2px">'
                f'      <span style="font-size:0.55rem;color:#3a5a7a;text-transform:uppercase">Index</span>'
                f'      <span style="font-size:0.95rem;font-weight:800;color:{tc}">{index_v}</span>'
                f'    </div>'
                f'    <div style="background:#0d1420;border-radius:2px;height:4px;overflow:hidden">'
                f'      <div style="width:{bar_mw};background:{bc};height:100%;border-radius:2px"></div>'
                f'    </div>'
                f'  </div>'
                f'</div>'
            )

        mid = (
            f'<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;padding:0 8px;gap:6px">'
            + (f'<div style="text-align:center"><div style="font-size:1.1rem;font-weight:900;color:#4caf82">{chunk_ratio}×</div><div style="font-size:0.52rem;color:#3a5a7a;text-transform:uppercase">fewer chunks</div></div>' if chunk_ratio else "")
            + (f'<div style="text-align:center"><div style="font-size:1.1rem;font-weight:900;color:#e8a838">{mb_ratio}×</div><div style="font-size:0.52rem;color:#3a5a7a;text-transform:uppercase">smaller index</div></div>' if mb_ratio else "")
            + f'</div>'
        )

        st.markdown(
            f'<div style="display:flex;gap:6px;align-items:stretch">'
            + _mini_card("⚡ EPIC", color, f"{epic_n:,}", f"{epic_mb} MB", epic_bar_w, epic_mb_w, color)
            + mid
            + _mini_card("Plain RAG", "#6a8aaa", f"{rag_n:,}", f"{rag_mb} MB", "100%", "100%", "#6a8aaa")
            + f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        st.info("⚠️ Index not built yet")

# ─── Query row ────────────────────────────────────────────────────────────────

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

q_col, btn_col = st.columns([5, 1])
with q_col:
    eq_cols = st.columns(len(EXAMPLE_QS))
    for col, q in zip(eq_cols, EXAMPLE_QS):
        short = q[:28] + "…" if len(q) > 28 else q
        if col.button(short, key=f"eq_{q[:12]}", use_container_width=True):
            st.session_state.query = q
            st.rerun()
    query = st.text_input(
        "question", value=st.session_state.query,
        placeholder="Ask anything — relationships, career, decisions, stress...",
        label_visibility="collapsed",
    )
    st.session_state.query = query

with btn_col:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run = st.button("⚡ Ask", type="primary",
                    disabled=not query.strip(), use_container_width=True)

# ─── Response panels — always at fixed position ───────────────────────────────

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

col_e, col_r = st.columns(2, gap="medium")

# Panel headers (static)
with col_e:
    st.markdown(
        f'<div class="method-header">'
        f'  <div class="method-dot" style="background:{color}"></div>'
        f'  <div>'
        f'    <span class="method-name" style="color:{color}">EPIC</span>'
        f'    <span style="font-size:0.65rem;color:#3a5a7a"> (Ours)</span>'
        f'    <div class="method-sub">Persona-aware indexing · preference-augmented retrieval</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    epic_chips_ph = st.empty()
    epic_pref_ph  = st.empty()
    epic_resp_ph  = st.empty()
    epic_eval_ph  = st.empty()
    epic_docs_ph  = st.empty()

with col_r:
    st.markdown(
        '<div class="method-header">'
        '  <div class="method-dot" style="background:#3a4a5a"></div>'
        '  <div>'
        '    <span class="method-name" style="color:#6a8aaa">Plain RAG</span>'
        '    <span style="font-size:0.65rem;color:#3a5a7a"> (Baseline)</span>'
        '    <div class="method-sub">No persona · vanilla retrieval · generic response</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )
    rag_chips_ph  = st.empty()
    rag_spacer_ph = st.empty()
    rag_resp_ph   = st.empty()
    rag_eval_ph   = st.empty()
    rag_docs_ph   = st.empty()

# ─── Helpers ─────────────────────────────────────────────────────────────────

res = st.session_state.result
er  = res["epic"]      if res else None
rr  = res["rag"]       if res else None
ee  = res.get("epic_eval") if res else None
re_ = res.get("rag_eval")  if res else None


def _chips(retr, gen, n_docs):
    return (
        f'<div style="display:flex;gap:4px;margin-bottom:5px;flex-wrap:wrap">'
        f'<div class="mchip"><span class="mchip-label">Retrieval</span><span class="mchip-value">{retr} ms</span></div>'
        f'<div class="mchip"><span class="mchip-label">Generation</span><span class="mchip-value">{gen} ms</span></div>'
        f'<div class="mchip"><span class="mchip-label">Docs</span><span class="mchip-value">{n_docs}</span></div>'
        f'</div>'
    )


def _eval_html(ev: dict) -> str:
    if not ev:
        return ""

    def badge(label, ok, neutral=False):
        if neutral:
            bg2, bdr, txt = "#0d1420", "#1a2535", "#3a5a7a"
            icon = "○"
        elif ok:
            bg2, bdr, txt = "#0a1f14", "#1a4a2a", "#4caf82"
            icon = "✓"
        else:
            bg2, bdr, txt = "#1f0a0a", "#4a1a1a", "#e05a5a"
            icon = "✗"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:3px;'
            f'background:{bg2};border:1px solid {bdr};border-radius:5px;'
            f'padding:2px 7px;font-size:0.6rem;color:{txt};margin:1px;font-weight:600">'
            f'{icon} {label}</span>'
        )

    acknow    = ev["acknow"]
    no_viol   = not ev["violate"]
    no_halluc = not ev["hallucinate"]
    helpful   = ev["helpful"]
    following = ev["preference_following"]

    row = (
        badge("Acknowledges Pref", acknow, neutral=not acknow)
        + badge("No Violation",     no_viol)
        + badge("No Hallucination", no_halluc, neutral=not acknow)
        + badge("Helpful",          helpful)
    )

    fc = "#4caf82" if following else "#e05a5a"
    fb = "#0a1f14" if following else "#1f0a0a"
    fd = "#1a4a2a" if following else "#4a1a1a"
    fi = "✓" if following else "✗"
    fl = "Preference Following" if following else "Preference Not Followed"

    summary = (
        f'<div style="margin-top:4px;display:inline-flex;align-items:center;gap:5px;'
        f'background:{fb};border:1px solid {fd};border-radius:6px;'
        f'padding:3px 10px;font-size:0.68rem;font-weight:700;color:{fc}">'
        f'{fi} {fl}</div>'
    )

    return (
        f'<div class="eval-section eval-animate">'
        f'<div class="eval-title">Preference Evaluation</div>'
        + row + summary +
        f'</div>'
    )


# ─── Populate panels based on state ───────────────────────────────────────────

def _doc_expander(ph, docs, accent_color, show_inst=False):
    if not docs:
        return
    lines = []
    for i, doc in enumerate(docs, 1):
        src  = doc.get("source","")
        sc   = doc.get("score", 0)
        txt  = doc.get("text","")[:200]
        inst = doc.get("instruction","")
        inst_html = f'<div class="doc-inst">📌 {inst}</div>' if (show_inst and inst) else ""
        lines.append(
            f'<div class="doc-card">'
            f'  <div class="doc-src">#{i} · {src} · {sc:.3f}</div>'
            + inst_html +
            f'  <div class="doc-txt">{txt}…</div>'
            f'</div>'
        )
    ph.markdown(
        f'<details style="margin-top:6px">'
        f'<summary style="font-size:0.68rem;color:{accent_color};cursor:pointer;user-select:none">'
        f'📂 Retrieved docs ({len(docs)})</summary>'
        f'<div style="margin-top:4px">{"".join(lines)}</div>'
        f'</details>',
        unsafe_allow_html=True,
    )


if er:
    epic_chips_ph.markdown(_chips(er["retr_ms"], er["gen_ms"], len(er["docs"])), unsafe_allow_html=True)
    if er.get("top_pref"):
        tp = er["top_pref"]
        short = (tp[:80] + "…") if len(tp) > 80 else tp
        epic_pref_ph.markdown(f'<div class="pref-match">🎯 {short}</div>', unsafe_allow_html=True)
    resp_html = er["response"].replace("\n", "<br>")
    epic_resp_ph.markdown(f'<div class="response-box resp-animate">{resp_html}</div>', unsafe_allow_html=True)
    if ee:
        epic_eval_ph.markdown(_eval_html(ee), unsafe_allow_html=True)
    _doc_expander(epic_docs_ph, er["docs"], color, show_inst=True)
else:
    epic_resp_ph.markdown(
        '<div class="response-box">'
        '<span class="response-placeholder">'
        'EPIC response — personalized to your MBTI type.<br><br>'
        '✦ Corpus filtered by persona preferences<br>'
        '✦ Query augmented with matched preference<br>'
        '✦ Generation guided by per-chunk instructions'
        '</span></div>',
        unsafe_allow_html=True,
    )

if rr:
    rag_chips_ph.markdown(_chips(rr["retr_ms"], rr["gen_ms"], len(rr["docs"])), unsafe_allow_html=True)
    rag_spacer_ph.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
    resp_html = rr["response"].replace("\n", "<br>")
    rag_resp_ph.markdown(f'<div class="response-box resp-animate" style="border-color:#141e2a">{resp_html}</div>', unsafe_allow_html=True)
    if re_:
        rag_eval_ph.markdown(_eval_html(re_), unsafe_allow_html=True)
    _doc_expander(rag_docs_ph, rr["docs"], "#6a8aaa", show_inst=False)
else:
    rag_resp_ph.markdown(
        '<div class="response-box" style="border-color:#141e2a">'
        '<span class="response-placeholder">'
        'Plain RAG response — no personalization.<br><br>'
        '✦ Same corpus, no preference filtering<br>'
        '✦ Standard cosine similarity retrieval<br>'
        '✦ Generic helpful-assistant prompt'
        '</span></div>',
        unsafe_allow_html=True,
    )

# ─── Run pipeline ─────────────────────────────────────────────────────────────

if run and query.strip():
    from src.retriever import epic_retrieve, rag_retrieve
    from src.generator import generate_epic, generate_rag
    from concurrent.futures import ThreadPoolExecutor, as_completed

    st.session_state.result = None

    # Show loading state in the fixed placeholders
    epic_chips_ph.empty()
    epic_pref_ph.empty()
    epic_eval_ph.empty()
    rag_chips_ph.empty()
    rag_spacer_ph.empty()
    rag_eval_ph.empty()

    epic_resp_ph.markdown(
        '<div class="response-box"><span class="response-placeholder">⏳ Retrieving &amp; generating…</span></div>',
        unsafe_allow_html=True,
    )
    rag_resp_ph.markdown(
        '<div class="response-box" style="border-color:#141e2a"><span class="response-placeholder">⏳ Retrieving &amp; generating…</span></div>',
        unsafe_allow_html=True,
    )

    def run_epic():
        r = epic_retrieve(query, mbti)
        t0 = time.perf_counter()
        resp = generate_epic(query, mbti, meta, r["docs"], backend=backend) if r.get("docs") else f"⚠️ EPIC index for {mbti} not found."
        return {"response": resp, "docs": r.get("docs",[]),
                "retr_ms": r.get("latency_ms",0), "gen_ms": round((time.perf_counter()-t0)*1000,1),
                "top_pref": r.get("top_preference","")}

    def run_rag():
        r = rag_retrieve(query)
        t0 = time.perf_counter()
        resp = generate_rag(query, r["docs"], backend=backend) if r.get("docs") else "⚠️ RAG index not found."
        return {"response": resp, "docs": r.get("docs",[]),
                "retr_ms": r.get("latency_ms",0), "gen_ms": round((time.perf_counter()-t0)*1000,1)}

    epic_result, rag_result = None, None

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(run_epic): "epic", ex.submit(run_rag): "rag"}
        for fut in as_completed(futures):
            tag  = futures[fut]
            data = fut.result()
            if tag == "epic":
                epic_result = data
                # Show response as soon as it's ready
                epic_chips_ph.markdown(_chips(data["retr_ms"], data["gen_ms"], len(data["docs"])), unsafe_allow_html=True)
                if data.get("top_pref"):
                    tp = data["top_pref"]
                    short = (tp[:80] + "…") if len(tp) > 80 else tp
                    epic_pref_ph.markdown(f'<div class="pref-match">🎯 {short}</div>', unsafe_allow_html=True)
                resp_html = data["response"].replace("\n", "<br>")
                epic_resp_ph.markdown(f'<div class="response-box resp-animate">{resp_html}</div>', unsafe_allow_html=True)
            else:
                rag_result = data
                rag_chips_ph.markdown(_chips(data["retr_ms"], data["gen_ms"], len(data["docs"])), unsafe_allow_html=True)
                rag_spacer_ph.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
                resp_html = data["response"].replace("\n", "<br>")
                rag_resp_ph.markdown(f'<div class="response-box resp-animate" style="border-color:#141e2a">{resp_html}</div>', unsafe_allow_html=True)

    # Evaluate both in parallel (responses dimmed momentarily by placeholder)
    from src.evaluator import evaluate_response
    top_pref = (epic_result or {}).get("top_pref", "")

    epic_eval_ph.markdown('<div class="eval-section"><div class="eval-title" style="color:#2a4a6a">⏳ Evaluating preference following…</div></div>', unsafe_allow_html=True)
    rag_eval_ph.markdown('<div class="eval-section"><div class="eval-title" style="color:#2a4a6a">⏳ Evaluating preference following…</div></div>', unsafe_allow_html=True)

    epic_eval, rag_eval = None, None
    eval_error = None
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fe = ex.submit(evaluate_response, query, top_pref, (epic_result or {}).get("response", ""), backend)
            fr = ex.submit(evaluate_response, query, top_pref, (rag_result or {}).get("response", ""), backend)
            epic_eval = fe.result()
            rag_eval  = fr.result()
        epic_eval_ph.markdown(_eval_html(epic_eval), unsafe_allow_html=True)
        rag_eval_ph.markdown(_eval_html(rag_eval),   unsafe_allow_html=True)
    except Exception as e:
        import traceback
        print(f"[eval] ERROR: {traceback.format_exc()}")
        err_html = f'<div class="eval-section"><div class="eval-title" style="color:#e05a5a">⚠️ Eval error: {e}</div></div>'
        epic_eval_ph.markdown(err_html, unsafe_allow_html=True)
        rag_eval_ph.markdown(err_html, unsafe_allow_html=True)

    st.session_state.result = {
        "query": query, "mbti": mbti,
        "epic": epic_result, "rag": rag_result,
        "epic_eval": epic_eval, "rag_eval": rag_eval,
        "top_pref": top_pref,
    }

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown(
    '<div style="text-align:center;padding:0.2rem 0 0;color:#1e2c3a;font-size:0.62rem">'
    'EPIC · Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp; ICML 2026'
    '</div>',
    unsafe_allow_html=True,
)
