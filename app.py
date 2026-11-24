
import os
import uuid
import html
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarizer import summarize, generate_title
from core.extractor import (
    extract_action_items,
    extract_key_decisions,
    extract_questions,
)
from core.rag_engine import build_rag_chain, ask_question

load_dotenv()

st.set_page_config(
    page_title="MeetMind AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------- CSS ----------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {
    --bg:#0a0a0f; --surface:#111118; --surface2:#1a1a25;
    --border:#2a2a3a; --accent:#7c3aed; --glow:#9f67ff;
    --cyan:#06b6d4; --text:#e8e8f0; --muted:#9a9ab8;
}
html,body,[class*="css"] {font-family:'JetBrains Mono',monospace;}
.stApp {background:var(--bg);color:var(--text);}
[data-testid="stSidebar"] {background:var(--surface);border-right:1px solid var(--border);}
[data-testid="stSidebar"] * {color:var(--text);}
.block-container {padding-top:1.7rem;max-width:1450px;}
h1,h2,h3,h4 {font-family:'Syne',sans-serif!important;color:var(--text)!important;}
.hero-title {
    font-family:'Syne',sans-serif;font-size:clamp(2rem,5vw,3.3rem);
    font-weight:800;background:linear-gradient(135deg,#fff,var(--glow),var(--cyan));
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-sub {color:var(--muted);font-size:.75rem;letter-spacing:.16em;margin-top:.5rem;}
.card {background:var(--surface);border:1px solid var(--border);border-radius:13px;padding:1.2rem;margin-bottom:.8rem;}
.card-title {font-family:'Syne',sans-serif;font-size:.7rem;letter-spacing:.12em;color:var(--muted);margin-bottom:.7rem;font-weight:700;}
.metric {background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1rem;min-height:100px;}
.metric-label {color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;}
.metric-value {font-family:'Syne',sans-serif;font-size:1.6rem;font-weight:800;color:white;margin-top:.4rem;}
.badge {display:inline-block;padding:.2rem .6rem;border-radius:5px;font-size:.65rem;letter-spacing:.08em;}
.purple {background:#7c3aed22;color:#c4a5ff;border:1px solid #7c3aed55;}
.cyan {background:#06b6d422;color:#67e8f9;border:1px solid #06b6d455;}
.green {background:#10b98122;color:#6ee7b7;border:1px solid #10b98155;}
.status-bar {padding:.65rem;background:var(--surface2);border:1px solid var(--border);border-radius:8px;margin:.35rem 0;font-size:.75rem;}
.dot {display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;}
.active {background:var(--glow);box-shadow:0 0 8px var(--glow);animation:pulse 1.2s infinite;}
.done {background:#10b981;}
.pending {background:#444;}
.error-dot {background:#ef4444;}
@keyframes pulse {50%{opacity:.35;}}
.stButton>button {border-radius:9px;font-family:'Syne',sans-serif!important;font-weight:700;min-height:42px;}
.stButton>button[kind="primary"] {background:linear-gradient(135deg,var(--accent),#5b21b6);border:0;color:white;}
.stTextInput input {background:var(--surface2)!important;}
div[data-testid="stChatMessage"] {background:var(--surface);border:1px solid var(--border);border-radius:12px;}
.stProgress>div>div>div {background:var(--accent)!important;}
hr {border-color:var(--border)!important;}
</style>
""", unsafe_allow_html=True)

# ---------------------- STATE ----------------------
for key, default in {
    "result": None,
    "chat_history": [],
    "pipeline_steps": {},
    "pipeline_done": False,
    "source_name": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

STEPS = [
    ("audio", "🔊 Audio Processing"),
    ("transcript", "📝 Transcription"),
    ("title", "🏷️ Title Generation"),
    ("summary", "📋 Summarization"),
    ("extract", "🔍 Insight Extraction"),
    ("rag", "🧠 RAG Knowledge Base"),
]

def set_step(key, state):
    st.session_state.pipeline_steps[key] = state

def render_steps():
    for key, label in STEPS:
        state = st.session_state.pipeline_steps.get(key, "pending")
        css = {"active":"active", "done":"done", "error":"error-dot"}.get(state, "pending")
        st.markdown(
            f'<div class="status-bar"><span class="dot {css}"></span>{label}</div>',
            unsafe_allow_html=True,
        )

def safe(value):
    return html.escape(str(value if value is not None else ""))

def render_items(value, empty_message):
    if not value:
        st.info(empty_message)
    elif isinstance(value, list):
        for i, item in enumerate(value, 1):
            st.markdown(f"**{i}.** {item}")
    else:
        st.markdown(str(value))

def save_upload(uploaded_file):
    folder = Path.cwd() / "uploads"
    folder.mkdir(exist_ok=True)
    suffix = Path(uploaded_file.name).suffix
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(uploaded_file.getbuffer())
    return str(path)

def make_report(r):
    return f"""# {r.get('title','Meeting Analysis')}

## Summary
{r.get('summary','')}

## Action Items
{r.get('action_items','')}

## Key Decisions
{r.get('key_decisions','')}

## Open Questions
{r.get('open_questions','')}

## Transcript
{r.get('transcript','')}
"""

# ---------------------- SIDEBAR ----------------------
with st.sidebar:
    st.markdown('<div class="hero-title" style="font-size:1.6rem">🎙️ MeetMind<br>AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">MEETING INTELLIGENCE</div>', unsafe_allow_html=True)
    st.divider()

    input_mode = st.radio("Input Source", ["YouTube URL", "Upload File"])

    youtube_url = ""
    uploaded_file = None

    if input_mode == "YouTube URL":
        youtube_url = st.text_input("YouTube link", placeholder="https://youtube.com/watch?v=...")
    else:
        uploaded_file = st.file_uploader(
            "Upload audio/video",
            type=["mp3","wav","m4a","mp4","mpeg","mpga","webm","mov","avi","mkv"]
        )

    language = st.selectbox(
        "Transcription Language",
        ["english", "hinglish"],
        format_func=lambda x: "English" if x == "english" else "Hindi / Hinglish"
    )

    analyze = st.button("⚡ ANALYZE CONTENT", type="primary", use_container_width=True)

    st.divider()
    st.markdown('<span class="badge purple">CAPABILITIES</span>', unsafe_allow_html=True)
    st.markdown("""
    - Audio/video transcription
    - English & Hinglish
    - AI summaries
    - Action-item extraction
    - Decision detection
    - Open-question extraction
    - RAG-based Q&A
    - Exportable reports
    """)

    if st.session_state.pipeline_steps:
        st.divider()
        st.markdown('<span class="badge green">PIPELINE STATUS</span>', unsafe_allow_html=True)
        render_steps()

    st.divider()
    st.caption("Whisper • LangChain • ChromaDB • Mistral AI")

# ---------------------- HEADER ----------------------
st.markdown('<div class="hero-title">MeetMind AI</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">TRANSCRIBE · SUMMARIZE · EXTRACT · ASK</div>', unsafe_allow_html=True)
st.divider()

# ---------------------- RUN PIPELINE ----------------------
if analyze:
    source = None

    if input_mode == "YouTube URL":
        if youtube_url.strip():
            source = youtube_url.strip()
        else:
            st.warning("Enter a YouTube URL.")
    elif uploaded_file:
        try:
            source = save_upload(uploaded_file)
            st.session_state.source_name = uploaded_file.name
        except Exception as e:
            st.error(f"Upload error: {e}")
    else:
        st.warning("Upload a file first.")

    if source:
        st.session_state.result = None
        st.session_state.chat_history = []
        st.session_state.pipeline_steps = {}
        st.session_state.pipeline_done = False

        progress = st.progress(0)
        status = st.empty()

        try:
            set_step("audio", "active")
            status.info("🔊 Processing audio...")
            st.write("DEBUG INPUT MODE:", input_mode)
            st.write("DEBUG SOURCE:", repr(source))
            st.write("DEBUG IS URL:", source.startswith(("http://", "https://")))

            chunks = process_input(source)
            set_step("audio", "done")
            progress.progress(15)

            set_step("transcript", "active")
            status.info("📝 Transcribing...")
            transcript = transcribe_all(chunks, language)

            if not transcript or not transcript.strip():
                raise ValueError("No transcript generated. Check the audio file.")

            set_step("transcript", "done")
            progress.progress(35)

            set_step("title", "active")
            status.info("🏷️ Generating title...")
            title = generate_title(transcript)
            set_step("title", "done")
            progress.progress(45)

            set_step("summary", "active")
            status.info("📋 Generating summary...")
            summary = summarize(transcript)
            set_step("summary", "done")
            progress.progress(60)

            set_step("extract", "active")
            status.info("🔍 Extracting insights...")
            action_items = extract_action_items(transcript)
            decisions = extract_key_decisions(transcript)
            questions = extract_questions(transcript)
            set_step("extract", "done")
            progress.progress(80)

            set_step("rag", "active")
            status.info("🧠 Building knowledge base...")
            rag_chain = build_rag_chain(transcript)
            set_step("rag", "done")
            progress.progress(100)

            st.session_state.result = {
                "title": title,
                "transcript": transcript,
                "summary": summary,
                "action_items": action_items,
                "key_decisions": decisions,
                "open_questions": questions,
                "rag_chain": rag_chain,
            }

            st.session_state.pipeline_done = True
            status.success("Analysis complete!")
            st.rerun()

        except Exception as e:
            for key, _ in STEPS:
                if st.session_state.pipeline_steps.get(key) == "active":
                    set_step(key, "error")
            status.error("Pipeline failed.")
            st.error(str(e))
            with st.expander("Technical error details"):
                st.exception(e)

# ---------------------- RESULTS ----------------------
r = st.session_state.result

if r:
    title = r.get("title", "Meeting Analysis")
    transcript = r.get("transcript", "")
    summary = r.get("summary", "")
    actions = r.get("action_items", [])
    decisions = r.get("key_decisions", [])
    questions = r.get("open_questions", [])

    st.markdown(
        f'<div class="card"><div class="card-title">SESSION TITLE</div><h2>{safe(title)}</h2></div>',
        unsafe_allow_html=True
    )

    metrics = st.columns(4)
    values = [
        ("Transcript Words", f"{len(transcript.split()):,}"),
        ("Action Items", len(actions) if isinstance(actions, list) else int(bool(actions))),
        ("Decisions", len(decisions) if isinstance(decisions, list) else int(bool(decisions))),
        ("Open Questions", len(questions) if isinstance(questions, list) else int(bool(questions))),
    ]

    for col, (label, value) in zip(metrics, values):
        with col:
            st.markdown(
                f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>',
                unsafe_allow_html=True
            )

    st.write("")

    tabs = st.tabs(["📊 Overview", "✅ Action Items", "🎯 Decisions", "📝 Transcript", "💬 AI Chat", "📥 Export"])

    # Overview
    with tabs[0]:
        col1, col2 = st.columns([1.6, 1])
        with col1:
            st.markdown("### Executive Summary")
            st.markdown(f'<div class="card"><div class="card-content">{safe(summary)}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown("### Quick Insights")
            st.markdown(f'<div class="card"><div class="card-title">ACTION ITEMS</div><div class="card-content">{safe(actions)}</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="card"><div class="card-title">KEY DECISIONS</div><div class="card-content">{safe(decisions)}</div></div>', unsafe_allow_html=True)

    # Action items
    with tabs[1]:
        st.markdown("### Tasks & Follow-ups")
        render_items(actions, "No action items extracted.")

    # Decisions/questions
    with tabs[2]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Key Decisions")
            render_items(decisions, "No decisions detected.")
        with col2:
            st.markdown("### Open Questions")
            render_items(questions, "No questions detected.")

    # Transcript
    with tabs[3]:
        search = st.text_input("🔎 Search transcript", placeholder="Search keywords...")
        if search:
            lower = transcript.lower()
            term = search.lower()
            matches = []
            start = 0
            while True:
                idx = lower.find(term, start)
                if idx < 0:
                    break
                matches.append(idx)
                start = idx + len(term)

            if matches:
                st.success(f"{len(matches)} match(es) found.")
                for idx in matches[:20]:
                    a = max(0, idx - 150)
                    b = min(len(transcript), idx + len(term) + 150)
                    snippet = safe(transcript[a:b])
                    snippet = snippet.replace(safe(search), f"<mark>{safe(search)}</mark>")
                    st.markdown(f'<div class="card">{snippet}</div>', unsafe_allow_html=True)
            else:
                st.warning("No matches found.")
        else:
            st.text_area("Transcript", transcript, height=450, label_visibility="collapsed")

    # RAG chat
    with tabs[4]:
        st.markdown("### Chat with your content")
        st.caption("Ask questions grounded in the processed transcript.")

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("Ask about this video or meeting...")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Searching and thinking..."):
                    try:
                        answer = ask_question(r["rag_chain"], prompt)
                        answer = str(answer) if answer is not None else "No relevant answer found."
                    except Exception as e:
                        answer = f"Could not answer: {e}"

                st.markdown(answer)

            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()

    # Downloads
    with tabs[5]:
        report = make_report(r)
        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                "📄 Full Report",
                report,
                file_name="meetmind_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "📝 Transcript",
                transcript,
                file_name="transcript.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col3:
            st.download_button(
                "📋 Summary",
                str(summary),
                file_name="summary.txt",
                mime="text/plain",
                use_container_width=True,
            )

else:
    st.markdown("""
    <div style="text-align:center;padding:4rem 1rem">
        <div style="font-size:4rem">🎬</div>
        <h2>Ready to Analyze</h2>
        <p style="color:#9a9ab8;max-width:550px;margin:auto;line-height:1.8">
        Paste a YouTube link or upload an audio/video file from the sidebar.
        MeetMind AI transforms long-form content into searchable knowledge.
        </p>
        <br>
        <span class="badge purple">TRANSCRIPTION</span>
        &nbsp; <span class="badge cyan">AI INSIGHTS</span>
        &nbsp; <span class="badge green">RAG CHAT</span>
    </div>
    """, unsafe_allow_html=True)
