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
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1rem 1.8rem 2rem; max-width: 1500px; }

.epic-header {
    background: linear-gradient(135deg, #0d1117 0%, #0d1f35 60%, #0f3460 100%);
    border: 1px solid #1e3a5f; border-radius: 16px;
    padding: 1.2rem 2rem; margin-bottom: 1rem;
    display: flex; align-items: center; justify-content: space-between;
}
.epic-logo { font-size: 1.7rem; font-weight: 800; color: #fff; letter-spacing: -1px; }
.epic-logo span { color: #4a90d9; }
.epic-tagline { font-size: 0.78rem; color: #5a8ab0; margin-top: 2px; }
.epic-badge {
    background: #0d2040; border: 1px solid #2d5080;
    border-radius: 8px; padding: 5px 12px;
    font-size: 0.75rem; color: #6aaad4; font-weight: 600;
}

.persona-banner {
    border-radius: 12px; padding: 0.9rem 1.3rem;
    margin: 0.6rem 0; display: flex; align-items: center; gap: 14px;
}
.persona-mbti { font-size: 1.8rem; font-weight: 800; }

/* Method panels — always visible */
.method-panel {
    border-radius: 14px; padding: 1.1rem 1.3rem; height: 100%;
    border: 1px solid #1a2535;
}
.method-header {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 10px; padding-bottom: 8px;
    border-bottom: 1px solid #1e2836;
}
.method-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.method-name { font-size: 1rem; font-weight: 700; }
.method-sub  { font-size: 0.7rem; color: #4a6a8a; margin-top: 1px; }

.mchip {
    background: #0d1420; border: 1px solid #1a2535;
    border-radius: 7px; padding: 4px 10px; font-size: 0.73rem;
    display: inline-block; margin: 2px;
}
.mchip-label { color: #3a5a7a; font-size: 0.65rem; display: block; }
.mchip-value { color: #a0c8e8; font-weight: 700; }

.response-box {
    background: #060b12; border: 1px solid #1a2535;
    border-radius: 10px; padding: 1rem 1.2rem;
    font-size: 0.86rem; line-height: 1.72; color: #c5d8ea;
    min-height: 160px;
}
.response-placeholder { color: #2a3a4a; font-style: italic; font-size: 0.82rem; }

.pref-match {
    background: #0a1e10; border: 1px solid #1a3a20;
    border-radius: 7px; padding: 5px 10px;
    font-size: 0.72rem; color: #4caf82; margin-bottom: 8px;
}

.doc-card {
    background: #060b12; border: 1px solid #111e2a;
    border-radius: 7px; padding: 7px 10px; margin-top: 5px;
}
.doc-src  { font-size: 0.66rem; color: #3a6a9a; font-weight: 600; margin-bottom: 2px; }
.doc-inst { font-size: 0.7rem; color: #3a8a5a; font-style: italic; margin-bottom: 3px; }
.doc-txt  { font-size: 0.73rem; color: #4a6a8a; line-height: 1.5; }

.metric-bar {
    background: #060b12; border: 1px solid #111e2a;
    border-radius: 10px; padding: 0.7rem 1.2rem;
    margin: 0.6rem 0; display: flex; gap: 24px; align-items: center; flex-wrap: wrap;
}
.stat-val   { font-size: 1.2rem; font-weight: 800; }
.stat-lbl   { font-size: 0.64rem; color: #3a5a7a; text-transform: uppercase; letter-spacing: 0.5px; }

div[data-testid="column"] button {
    border-radius: 9px !important; font-size: 0.79rem !important;
    font-weight: 700 !important; padding: 5px 4px !important;
}
hr.divider { border: none; border-top: 1px solid #111e2a; margin: 0.8rem 0; }
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
    <div class="epic-tagline">
      Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp;
      Same question, different answers for different personalities
    </div>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <div class="epic-badge">🏆 ICML 2026</div>
    <div class="epic-badge">🔵 EPIC &nbsp;vs&nbsp; ⚪ Plain RAG</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── MBTI selector + backend ──────────────────────────────────────────────────

col_mbti, col_back = st.columns([5, 1])

with col_back:
    st.markdown("**LLM Backend**")
    backend = st.radio("backend", ["vllm", "claude", "ollama"],
                       index=["vllm","claude","ollama"].index(st.session_state.backend),
                       label_visibility="collapsed")
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
            if col.button(label, key=f"mbti_{t}",
                          type="primary" if is_sel else "secondary",
                          use_container_width=True):
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
    f'    <div style="font-size:0.95rem;font-weight:700;color:{color}">{meta["label"]}</div>'
    f'    <div style="font-size:0.78rem;color:#8a9ab0">{meta["description"]}</div>'
    f'  </div>'
    f'</div>',
    unsafe_allow_html=True,
)

with st.expander("📋 Preferences used for EPIC indexing", expanded=False):
    tags = "".join(
        f'<span style="display:inline-block;border-radius:6px;padding:3px 9px;margin:2px;'
        f'background:{bg};border:1px solid {color}44;color:{color}cc;font-size:0.72rem">'
        f'• {p}</span>'
        for p in meta["preferences"]
    )
    st.markdown(f'<div style="line-height:2.2">{tags}</div>', unsafe_allow_html=True)

# ─── Index stats + compression viz ───────────────────────────────────────────

try:
    from src.retriever import get_index_stats
    stats = get_index_stats(mbti)
    epic_n       = stats.get("epic_indexed_chunks", 0)
    total_n      = stats.get("epic_total_input", 0)
    rag_n        = stats.get("rag_total_chunks", 0)
    epic_mb      = stats.get("epic_total_mb", 0)
    rag_mb       = stats.get("rag_index_mb", 0)
    chunk_ratio = round(rag_n / epic_n) if epic_n else 0
    mb_ratio    = round(rag_mb / epic_mb) if epic_mb else 0

    # Two-panel comparison card matching the left/right response layout
    epic_bar_w = f"{max(2, round(epic_n / rag_n * 100))}%" if rag_n else "2%"
    epic_mb_w  = f"{max(2, round(epic_mb / rag_mb * 100))}%" if rag_mb else "2%"

    def mini_card(title, title_color, chunks_val, index_val, bar_chunk_w, bar_mb_w, bar_color):
        return (
            f'<div style="flex:1;background:#060b12;border:1px solid {title_color}30;'
            f'border-radius:10px;padding:12px 16px">'
            f'  <div style="font-size:0.68rem;font-weight:800;color:{title_color};'
            f'text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">{title}</div>'
            f'  <div style="margin-bottom:8px">'
            f'    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px">'
            f'      <span style="font-size:0.6rem;color:#3a5a7a;text-transform:uppercase">Chunks</span>'
            f'      <span style="font-size:1.05rem;font-weight:800;color:{title_color}">{chunks_val}</span>'
            f'    </div>'
            f'    <div style="background:#0d1420;border-radius:3px;height:5px;overflow:hidden">'
            f'      <div style="width:{bar_chunk_w};background:{bar_color};height:100%;border-radius:3px"></div>'
            f'    </div>'
            f'  </div>'
            f'  <div>'
            f'    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px">'
            f'      <span style="font-size:0.6rem;color:#3a5a7a;text-transform:uppercase">Index Size</span>'
            f'      <span style="font-size:1.05rem;font-weight:800;color:{title_color}">{index_val}</span>'
            f'    </div>'
            f'    <div style="background:#0d1420;border-radius:3px;height:5px;overflow:hidden">'
            f'      <div style="width:{bar_mb_w};background:{bar_color};height:100%;border-radius:3px"></div>'
            f'    </div>'
            f'  </div>'
            f'</div>'
        )

    chunk_arrow = f'<div style="text-align:center;margin-bottom:6px"><div style="font-size:1.3rem;font-weight:900;color:#4caf82">{chunk_ratio}×</div><div style="font-size:0.58rem;color:#3a5a7a;text-transform:uppercase;letter-spacing:0.5px">fewer chunks</div></div>' if chunk_ratio else ""
    mb_arrow    = f'<div style="text-align:center"><div style="font-size:1.3rem;font-weight:900;color:#e8a838">{mb_ratio}×</div><div style="font-size:0.58rem;color:#3a5a7a;text-transform:uppercase;letter-spacing:0.5px">smaller index</div></div>' if mb_ratio else ""

    mid_col = (
        f'<div style="display:flex;flex-direction:column;justify-content:center;align-items:center;'
        f'padding:0 10px;min-width:90px">'
        + chunk_arrow
        + mb_arrow
        + f'</div>'
    )

    st.markdown(
        f'<div style="display:flex;gap:8px;align-items:stretch;margin-bottom:8px">'
        + mini_card("⚡ EPIC", color, f"{epic_n:,}", f"{epic_mb} MB", epic_bar_w, epic_mb_w, color)
        + mid_col
        + mini_card("Plain RAG", "#6a8aaa", f"{rag_n:,}", f"{rag_mb} MB", "100%", "100%", "#6a8aaa")
        + f'</div>',
        unsafe_allow_html=True,
    )
except Exception:
    st.info("⚠️ Index not built yet — run `python run_pipeline.py --steps index_epic,index_rag` first")

# ─── Query input ──────────────────────────────────────────────────────────────

st.markdown("<hr class='divider'>", unsafe_allow_html=True)
st.markdown("**Try a question** — or pick one:")

eq_cols = st.columns(len(EXAMPLE_QS))
for col, q in zip(eq_cols, EXAMPLE_QS):
    short = q[:32] + "…" if len(q) > 32 else q
    if col.button(short, key=f"eq_{q[:12]}", use_container_width=True):
        st.session_state.query = q
        st.rerun()

query = st.text_input(
    "question", value=st.session_state.query,
    placeholder="Ask anything — relationships, career, decisions, stress...",
    label_visibility="collapsed",
)
st.session_state.query = query

run = st.button("⚡  Generate Personalized Response", type="primary",
                disabled=not query.strip(), use_container_width=True)

# ─── Run pipeline (parallel, show first-ready first) ─────────────────────────

if run and query.strip():
    from src.retriever import epic_retrieve, rag_retrieve
    from src.generator import generate_epic, generate_rag
    from concurrent.futures import ThreadPoolExecutor, as_completed

    st.session_state.result = None  # clear old result

    # Placeholders — rendered immediately, filled as results arrive
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    col_e_live, col_r_live = st.columns(2)

    def _panel_header(col, title, subtitle, col_color):
        col.markdown(
            f'<div class="method-header">'
            f'  <div class="method-dot" style="background:{col_color}"></div>'
            f'  <div><div class="method-name" style="color:{col_color}">{title}</div>'
            f'  <div class="method-sub">{subtitle}</div></div></div>',
            unsafe_allow_html=True,
        )

    _panel_header(col_e_live,
                  f'EPIC <span style="font-size:0.72rem;font-weight:400;color:#3a5a7a">(Ours)</span>',
                  "Persona-aware indexing · preference-augmented retrieval",
                  color)
    _panel_header(col_r_live,
                  'Plain RAG <span style="font-size:0.72rem;font-weight:400;color:#3a5a7a">(Baseline)</span>',
                  "No persona · vanilla retrieval · generic response",
                  "#6a8aaa")

    epic_ph = col_e_live.empty()
    rag_ph  = col_r_live.empty()

    epic_ph.markdown('<div class="response-box"><span class="response-placeholder">⏳ Generating…</span></div>', unsafe_allow_html=True)
    rag_ph.markdown( '<div class="response-box"><span class="response-placeholder">⏳ Generating…</span></div>', unsafe_allow_html=True)

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

    def _render_epic(data, ph):
        retr, gen = data["retr_ms"], data["gen_ms"]
        pref_html = f'<div class="pref-match">🎯 {data["top_pref"][:75]}…</div>' if data.get("top_pref") else ""
        chips = (f'<div style="display:flex;gap:6px;margin-bottom:8px">'
                 f'<div class="mchip"><span class="mchip-label">Retrieval</span><span class="mchip-value">{retr} ms</span></div>'
                 f'<div class="mchip"><span class="mchip-label">Generation</span><span class="mchip-value">{gen} ms</span></div>'
                 f'<div class="mchip"><span class="mchip-label">Docs</span><span class="mchip-value">{len(data["docs"])}</span></div>'
                 f'</div>')
        resp_html = data["response"].replace("\n", "<br>")
        ph.markdown(chips + pref_html + f'<div class="response-box">{resp_html}</div>', unsafe_allow_html=True)

    def _render_rag(data, ph):
        retr, gen = data["retr_ms"], data["gen_ms"]
        chips = (f'<div style="display:flex;gap:6px;margin-bottom:8px">'
                 f'<div class="mchip"><span class="mchip-label">Retrieval</span><span class="mchip-value">{retr} ms</span></div>'
                 f'<div class="mchip"><span class="mchip-label">Generation</span><span class="mchip-value">{gen} ms</span></div>'
                 f'<div class="mchip"><span class="mchip-label">Docs</span><span class="mchip-value">{len(data["docs"])}</span></div>'
                 f'</div>')
        resp_html = data["response"].replace("\n", "<br>")
        ph.markdown(chips + '<div style="height:29px"></div>' + f'<div class="response-box" style="border-color:#141e2a">{resp_html}</div>', unsafe_allow_html=True)

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(run_epic): "epic", ex.submit(run_rag): "rag"}
        for fut in as_completed(futures):
            tag  = futures[fut]
            data = fut.result()
            if tag == "epic":
                epic_result = data
                _render_epic(data, epic_ph)
            else:
                rag_result = data
                _render_rag(data, rag_ph)

    # Run preference-following evaluation for both responses in parallel
    from src.evaluator import evaluate_response
    top_pref = (epic_result or {}).get("top_pref", "")
    eval_ph_e = col_e_live.empty()
    eval_ph_r = col_r_live.empty()
    eval_ph_e.markdown('<div style="font-size:0.7rem;color:#3a5a7a;margin-top:6px">⏳ Evaluating preference following…</div>', unsafe_allow_html=True)
    eval_ph_r.markdown('<div style="font-size:0.7rem;color:#3a5a7a;margin-top:6px">⏳ Evaluating preference following…</div>', unsafe_allow_html=True)

    def _eval(response):
        return evaluate_response(query, top_pref, response)

    epic_eval, rag_eval = None, None
    with ThreadPoolExecutor(max_workers=2) as ex:
        fe = ex.submit(_eval, (epic_result or {}).get("response", ""))
        fr = ex.submit(_eval, (rag_result or {}).get("response", ""))
        epic_eval = fe.result()
        rag_eval  = fr.result()

    eval_ph_e.empty()
    eval_ph_r.empty()

    st.session_state.result = {
        "query": query, "mbti": mbti,
        "epic": epic_result, "rag": rag_result,
        "epic_eval": epic_eval, "rag_eval": rag_eval,
        "top_pref": top_pref,
    }
    st.rerun()

# ─── Always-visible side-by-side panels ───────────────────────────────────────

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

res = st.session_state.result
er  = res["epic"]      if res else None
rr  = res["rag"]       if res else None
ee  = res.get("epic_eval") if res else None
re_ = res.get("rag_eval")  if res else None


def _eval_badges(ev: dict, panel_color: str) -> str:
    """Render preference-following evaluation as HTML badges."""
    if not ev:
        return ""

    def badge(label, ok, neutral=False):
        if neutral:
            bg, border, txt = "#0d1420", "#1a2535", "#3a5a7a"
            icon = "○"
        elif ok:
            bg, border, txt = "#0a1f14", "#1a4a2a", "#4caf82"
            icon = "✓"
        else:
            bg, border, txt = "#1f0a0a", "#4a1a1a", "#e05a5a"
            icon = "✗"
        return (
            f'<div style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{bg};border:1px solid {border};border-radius:6px;'
            f'padding:3px 8px;font-size:0.65rem;color:{txt};margin:2px">'
            f'<span style="font-weight:700">{icon}</span> {label}</div>'
        )

    acknow    = ev["acknow"]
    no_viol   = not ev["violate"]
    no_halluc = not ev["hallucinate"]
    helpful   = ev["helpful"]
    following = ev["preference_following"]

    row = (
        badge("Acknowledges Pref", acknow, neutral=not acknow)
        + badge("No Violation",    no_viol)
        + badge("No Hallucination",no_halluc, neutral=not acknow)
        + badge("Helpful",         helpful)
    )

    follow_color = "#4caf82" if following else "#e05a5a"
    follow_bg    = "#0a1f14" if following else "#1f0a0a"
    follow_bd    = "#1a4a2a" if following else "#4a1a1a"
    follow_icon  = "✓" if following else "✗"
    follow_label = "Preference Following" if following else "Preference Not Followed"

    summary = (
        f'<div style="margin-top:6px;display:inline-flex;align-items:center;gap:6px;'
        f'background:{follow_bg};border:1px solid {follow_bd};border-radius:8px;'
        f'padding:5px 12px;font-size:0.72rem;font-weight:700;color:{follow_color}">'
        f'<span style="font-size:1rem">{follow_icon}</span> {follow_label}</div>'
    )

    return (
        f'<div style="margin-top:8px;padding:8px 10px;background:#060b12;'
        f'border:1px solid #111e2a;border-radius:8px">'
        f'<div style="font-size:0.6rem;color:#3a5a7a;text-transform:uppercase;'
        f'letter-spacing:0.5px;margin-bottom:4px">Preference Evaluation</div>'
        + row + summary +
        f'</div>'
    )

col_e, col_r = st.columns(2)

# ── EPIC panel ────────────────────────────────────────────────────────────────
with col_e:
    st.markdown(
        f'<div class="method-header">'
        f'  <div class="method-dot" style="background:{color}"></div>'
        f'  <div>'
        f'    <div class="method-name" style="color:{color}">EPIC &nbsp;<span style="font-size:0.72rem;font-weight:400;color:#3a5a7a">(Ours)</span></div>'
        f'    <div class="method-sub">Persona-aware indexing · preference-augmented retrieval · instruction-guided generation</div>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if er:
        # Metrics row
        retr = er["retr_ms"]
        gen  = er["gen_ms"]
        total = round(retr + gen, 1)
        st.markdown(
            f'<div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">'
            f'  <div class="mchip"><span class="mchip-label">Retrieval</span><span class="mchip-value">{retr} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Generation</span><span class="mchip-value">{gen} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Total</span><span class="mchip-value">{total} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Docs</span><span class="mchip-value">{len(er["docs"])}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if er.get("top_pref"):
            tp = er["top_pref"]
            short_pref = (tp[:75] + "…") if len(tp) > 75 else tp
            st.markdown(f'<div class="pref-match">🎯 {short_pref}</div>', unsafe_allow_html=True)

        resp_html = er["response"].replace("\n", "<br>")
        st.markdown(f'<div class="response-box">{resp_html}</div>', unsafe_allow_html=True)
        if ee:
            st.markdown(_eval_badges(ee, color), unsafe_allow_html=True)

        if er["docs"]:
            with st.expander(f"📂 Retrieved docs ({len(er['docs'])})", expanded=False):
                for i, doc in enumerate(er["docs"], 1):
                    src  = doc.get("source","")
                    inst = doc.get("instruction","")
                    sc   = doc.get("score", 0)
                    txt  = doc.get("text","")[:200]
                    inst_html = f'<div class="doc-inst">📌 {inst}</div>' if inst else ""
                    st.markdown(
                        f'<div class="doc-card">'
                        f'  <div class="doc-src">#{i} · {src} · {sc:.3f}</div>'
                        f'  {inst_html}'
                        f'  <div class="doc-txt">{txt}…</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            '<div class="response-box">'
            '<span class="response-placeholder">'
            'EPIC response will appear here — personalized to your MBTI type.<br><br>'
            '✦ Filters corpus by persona preferences<br>'
            '✦ Augments query with matched preference<br>'
            '✦ Guides generation with per-chunk instructions'
            '</span></div>',
            unsafe_allow_html=True,
        )

# ── Plain RAG panel ───────────────────────────────────────────────────────────
with col_r:
    st.markdown(
        '<div class="method-header">'
        '  <div class="method-dot" style="background:#3a4a5a"></div>'
        '  <div>'
        '    <div class="method-name" style="color:#6a8aaa">Plain RAG &nbsp;<span style="font-size:0.72rem;font-weight:400;color:#3a5a7a">(Baseline)</span></div>'
        '    <div class="method-sub">No persona · vanilla retrieval · generic response</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if rr:
        retr = rr["retr_ms"]
        gen  = rr["gen_ms"]
        total = round(retr + gen, 1)
        st.markdown(
            f'<div style="display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap">'
            f'  <div class="mchip"><span class="mchip-label">Retrieval</span><span class="mchip-value">{retr} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Generation</span><span class="mchip-value">{gen} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Total</span><span class="mchip-value">{total} ms</span></div>'
            f'  <div class="mchip"><span class="mchip-label">Docs</span><span class="mchip-value">{len(rr["docs"])}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Spacer to align with EPIC's pref-match badge height
        st.markdown('<div style="height:29px"></div>', unsafe_allow_html=True)

        resp_html = rr["response"].replace("\n", "<br>")
        st.markdown(
            f'<div class="response-box" style="border-color:#141e2a">{resp_html}</div>',
            unsafe_allow_html=True,
        )
        if re_:
            st.markdown(_eval_badges(re_, "#6a8aaa"), unsafe_allow_html=True)

        if rr["docs"]:
            with st.expander(f"📂 Retrieved docs ({len(rr['docs'])})", expanded=False):
                for i, doc in enumerate(rr["docs"], 1):
                    src = doc.get("source","")
                    sc  = doc.get("score", 0)
                    txt = doc.get("text","")[:200]
                    st.markdown(
                        f'<div class="doc-card">'
                        f'  <div class="doc-src">#{i} · {src} · {sc:.3f}</div>'
                        f'  <div class="doc-txt">{txt}…</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            '<div class="response-box" style="border-color:#141e2a">'
            '<span class="response-placeholder">'
            'Plain RAG response will appear here — no personalization.<br><br>'
            '✦ Same corpus, no preference filtering<br>'
            '✦ Standard cosine similarity retrieval<br>'
            '✦ Generic helpful-assistant prompt'
            '</span></div>',
            unsafe_allow_html=True,
        )


# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;padding:1.2rem 0 0.4rem;color:#1e2c3a;font-size:0.7rem">
  EPIC · Embedding-based Personal Indexing &amp; Curation &nbsp;·&nbsp; ICML 2026
</div>
""", unsafe_allow_html=True)
