import streamlit as st
import requests
import json
import time
import sqlite3
import datetime
import base64
import re
import pandas as pd
from fpdf import FPDF

try:
    from vector_store import (
        save_question, search_similar,
        get_all_questions, count_questions, total_questions_all
    )
    VECTOR_DB = True
except ImportError:
    VECTOR_DB = False

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "llama3"
DB_PATH         = "interview_bot.db"

INTERVIEW_TYPES   = ["Software Engineering / Coding", "Data Science / ML", "System Design", "HR / Behavioral"]
DIFFICULTY_LEVELS = ["Beginner", "Intermediate", "Advanced"]
EXPERIENCE_LEVELS = ["Fresher (0-1 yr)", "Junior (1-3 yrs)", "Mid (3-5 yrs)", "Senior (5+ yrs)"]
COMPANIES         = ["None (General)", "Google", "Amazon", "Microsoft", "Meta", "Netflix", "Apple", "Flipkart", "Infosys", "TCS", "Wipro"]

st.set_page_config(page_title="Interview Prep Bot", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.main-header{font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stButton>button{border-radius:8px;font-weight:500}
.hint-box{background:#fffbea;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:0 8px 8px 0;margin:8px 0;font-size:.95rem}
.flash-front{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-radius:16px;padding:2rem;text-align:center;min-height:180px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:500;margin:10px 0}
.flash-back{background:linear-gradient(135deg,#11998e,#38ef7d);color:white;border-radius:16px;padding:2rem;text-align:center;min-height:180px;display:flex;align-items:center;justify-content:center;font-size:1rem;margin:10px 0}
.company-badge{background:#e0e7ff;color:#3730a3;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;display:inline-block;margin-bottom:12px}
.timer-green{font-size:3rem;font-weight:800;color:#22c55e;text-align:center;font-family:monospace}
.timer-red{font-size:3rem;font-weight:800;color:#ef4444;text-align:center;font-family:monospace}
.nav-page-title{font-size:1.6rem;font-weight:700;margin-bottom:.4rem;color:#1e293b}
.qbank-card{background:#f8faff;border:1px solid #e2e8f0;border-radius:12px;padding:1rem;margin:6px 0}
div[data-testid="stSidebar"]{background:#f8faff}
</style>
""", unsafe_allow_html=True)

# ── DATABASE ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        interview_type TEXT,
        topic TEXT,
        question TEXT,
        answer TEXT,
        score INTEGER,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    conn.commit(); conn.close()

def get_or_create_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if row: conn.close(); return row[0]
    c.execute("INSERT INTO users(username,created_at) VALUES(?,?)",
              (username, datetime.datetime.now().isoformat()))
    conn.commit(); uid = c.lastrowid; conn.close(); return uid

def save_session(user_id, interview_type, topic, question, answer, score):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO sessions(user_id,interview_type,topic,question,answer,score,created_at)
                 VALUES(?,?,?,?,?,?,?)""",
              (user_id, interview_type, topic, question, answer, score,
               datetime.datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_user_sessions(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT interview_type,topic,question,answer,score,created_at
                 FROM sessions WHERE user_id=? ORDER BY created_at DESC""", (user_id,))
    rows = c.fetchall(); conn.close(); return rows

# ── OLLAMA ────────────────────────────────────────────────────────────────────
def check_ollama():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except: return False

def call_ollama(prompt):
    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/generate",
                          json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                          timeout=180)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return "❌ Cannot connect to Ollama. Run: ollama serve"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def call_ollama_stream(prompt):
    try:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/generate",
                          json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
                          timeout=180, stream=True)
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                yield data.get("response", "")
                if data.get("done"): break
    except Exception as e:
        yield f"❌ Error: {str(e)}"

# ── PROMPTS ───────────────────────────────────────────────────────────────────
def prompt_questions(interview_type, topic, difficulty, experience, company):
    cn = f" tailored for {company} interview style" if company != "None (General)" else ""
    if interview_type == "Software Engineering / Coding":
        return f"""You are an expert technical interviewer{cn}.
Generate 3 {difficulty} level coding interview questions for a {experience} candidate on: {topic}.
For each question:
Q1: [Question]
Hint: [Subtle hint]
Tests: [Concept tested]
Repeat for Q2, Q3."""
    elif interview_type == "HR / Behavioral":
        return f"""You are an experienced HR interviewer{cn}.
Generate 5 behavioral questions using STAR method for a {experience} {topic} candidate.
For each: state the question, what the interviewer looks for, answer framework."""
    elif interview_type == "System Design":
        return f"""You are a system design expert{cn}.
Generate a system design question about {topic} for a {experience} candidate.
Include: problem statement, requirements, key components, follow-ups, evaluation criteria."""
    elif interview_type == "Data Science / ML":
        return f"""You are a DS/ML interview expert{cn}.
Generate 3 {difficulty} DS/ML questions on {topic} for a {experience} candidate.
For each: question, key points a strong answer covers, common mistakes."""
    return f"Generate 3 {difficulty} interview questions on {topic} for {experience}{cn}."

def prompt_evaluate(question, answer, interview_type):
    return f"""You are a strict but fair {interview_type} interviewer evaluating a candidate.

Question: {question}
Candidate Answer: {answer}

Evaluate on:
1. Correctness (0-10)
2. Depth & Detail (0-10)
3. Communication Clarity (0-10)
4. Overall Score (0-10)

Provide: what was done well, what was missing, a model answer.
Start your response with: SCORE: X/10"""

def prompt_roadmap(role, experience, timeline, company):
    cn = f" targeting {company}" if company != "None (General)" else ""
    return f"""Create a detailed interview prep roadmap for a {experience} {role}{cn} with {timeline} to prepare.
Include: week-by-week plan, topics (High/Medium/Low priority), resources, mock interview schedule, tips for all round types."""

def prompt_jd(jd):
    return f"""Analyze this job description and extract:
1. Top 5 required technical skills
2. Top 3 soft skills expected
3. 5 targeted interview questions based on this JD
4. What the hiring team is prioritizing

Job Description:
{jd}"""

def prompt_resume(resume, interview_type):
    return f"""Based on this resume, generate 5 personalized {interview_type} interview questions.
For each explain why it is relevant to their background.

Resume:
{resume}"""

def prompt_mock_next(history, interview_type, topic, qnum):
    hist = "\n".join([f"Q{i+1}: {h['q']}\nA: {h['a']}" for i, h in enumerate(history)])
    prev = f"Previous Q&A:\n{hist}\n\n" if hist else ""
    return f"""You are conducting a {interview_type} mock interview on: {topic}.
{prev}Ask question {qnum}, progressively harder than previous ones.
Ask ONLY the question, nothing else."""

def prompt_hint(question, hints):
    prev = f" Previous hints: {'; '.join(hints)}." if hints else ""
    return f"""For this interview question: "{question}"{prev}
Give ONE new subtle hint without revealing the answer.
Start with "Hint {len(hints)+1}:" Keep it 1-2 sentences only."""

def prompt_flashcards(topic, interview_type, n=8):
    return f"""Generate {n} flashcards for {interview_type} revision on: {topic}.
Format EXACTLY like this for every card:
FRONT: [question or concept]
BACK: [concise answer, max 3 sentences]
---
Output only cards in this format. No extra text."""

def prompt_company(company, role, experience):
    return f"""Generate 5 interview questions specifically asked at {company} for {role} ({experience}).
Include: what makes {company}'s interview unique, 3 tips to crack it, what {company} looks for."""

# ── HELPERS ───────────────────────────────────────────────────────────────────
def extract_score(text):
    m = re.search(r"SCORE:\s*(\d+)", text)
    return int(m.group(1)) if m else 0

def generate_pdf(title, content):
    pdf = FPDF(); pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Arial", size=11); pdf.ln(4)
    for line in content.split("\n"):
        safe = line.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 7, safe)
    return pdf.output(dest="S").encode("latin-1")

def pdf_download_btn(title, content, filename):
    if not content: st.info("No content to export yet."); return
    b64 = base64.b64encode(generate_pdf(title, content)).decode()
    st.markdown(
        f'<a href="data:application/pdf;base64,{b64}" download="{filename}" '
        f'style="display:inline-block;padding:8px 20px;background:#6366f1;color:white;'
        f'border-radius:8px;text-decoration:none;font-weight:600;">📥 Download PDF</a>',
        unsafe_allow_html=True)

def stream_response(prompt, header=None):
    if header: st.markdown(f"### {header}")
    ph = st.empty(); full = ""
    for chunk in call_ollama_stream(prompt):
        full += chunk; ph.markdown(full + "▌")
    ph.markdown(full); return full

# ── SESSION STATE INIT ────────────────────────────────────────────────────────
init_db()
defaults = {
    "username": "", "user_id": None,
    "mock_history": [], "mock_qnum": 1, "mock_current_q": "",
    "hints": [],
    "flash_idx": 0, "flash_show_back": False, "flashcards": [],
    "timer_running": False, "timer_start": 0, "timer_limit": 120,
    "timed_question": "", "timed_submitted": False,
    "last_q_block": "", "roadmap_result": "",
    "jd_result": "", "company_result": "",
    "eval_prefill": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🎯 Interview Preparation Bot</div>', unsafe_allow_html=True)
st.markdown("*Powered by Ollama + LLaMA 3 — Your personal AI interview coach*")

if not check_ollama():
    st.error("❌ Ollama not running! Open a terminal and run: `ollama serve`")
    st.stop()
else:
    st.success("✅ Ollama connected — LLaMA 3 ready!")

if VECTOR_DB:
    st.info(f"🧠 Vector DB active — {total_questions_all()} questions stored")

st.divider()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👤 User Profile")
    uname = st.text_input("Your name", value=st.session_state.username, placeholder="e.g. Rahul")
    if st.button("🔐 Login / Switch", use_container_width=True):
        if uname.strip():
            st.session_state.username = uname.strip()
            st.session_state.user_id  = get_or_create_user(uname.strip())
            st.success(f"Welcome, {uname.strip()}! 👋")
    if st.session_state.user_id:
        st.info(f"Logged in as **{st.session_state.username}**")

    st.divider()
    st.markdown("## ⚙️ Settings")
    experience     = st.selectbox("Experience Level", EXPERIENCE_LEVELS)
    interview_type = st.selectbox("Interview Type",   INTERVIEW_TYPES)
    difficulty     = st.selectbox("Difficulty",       DIFFICULTY_LEVELS)
    topic          = st.text_input("Topic / Role", placeholder="e.g. Python, ML, DSA")
    company        = st.selectbox("Target Company",   COMPANIES)

    if VECTOR_DB:
        st.divider()
        st.markdown("## 🧠 Question Bank")
        st.metric("Stored (this type)", count_questions(interview_type))
        st.metric("Total stored", total_questions_all())

    st.divider()
    st.markdown("## 🗺️ Navigate")
    pages = [
        "📋 Generate Questions",
        "🎭 Mock Interview",
        "✍️ Evaluate Answer",
        "💡 Hints Mode",
        "🃏 Flashcards",
        "📄 JD Analyzer",
        "📑 Resume Questions",
        "🏢 Company Prep",
        "🗺️ Study Roadmap",
        "📊 Score Dashboard",
        "⏱️ Timed Mode",
        "📥 Export PDF",
    ]
    if VECTOR_DB:
        pages.insert(-1, "🧠 Question Bank")
    page = st.radio("", pages, label_visibility="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — GENERATE QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
if page == "📋 Generate Questions":
    st.markdown('<div class="nav-page-title">📋 Question Generator</div>', unsafe_allow_html=True)
    st.caption("Generate targeted interview questions based on your settings.")

    if st.button("🚀 Generate Questions", use_container_width=True, type="primary"):
        if not topic:
            st.warning("⚠️ Please enter a topic in the sidebar.")
        else:
            prompt = prompt_questions(interview_type, topic, difficulty, experience, company)
            result = stream_response(prompt, "📌 Your Interview Questions")
            st.session_state.last_q_block = result

            if VECTOR_DB and result and not result.startswith("❌"):
                save_question(interview_type, topic, result, difficulty, experience)
                st.caption("✅ Saved to vector question bank")

    if st.session_state.last_q_block:
        st.divider()
        if VECTOR_DB:
            st.markdown("#### 🔍 Find Similar Past Questions")
            if st.button("Search similar in Question Bank"):
                results = search_similar(interview_type, topic or "general", n_results=3)
                for doc, meta in results:
                    with st.expander(f"Similar — {meta.get('topic','')} | {meta.get('difficulty','')}"):
                        st.markdown(doc)
        pdf_download_btn("Interview Questions", st.session_state.last_q_block, "questions.pdf")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — MOCK INTERVIEW
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎭 Mock Interview":
    st.markdown('<div class="nav-page-title">🎭 Mock Interview Mode</div>', unsafe_allow_html=True)
    st.caption("The bot asks 5 questions one by one — just like a real interview.")

    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Reset"):
            st.session_state.mock_history   = []
            st.session_state.mock_qnum      = 1
            st.session_state.mock_current_q = ""
            st.rerun()

    if not topic:
        st.warning("⚠️ Set a topic in the sidebar first.")
    else:
        if not st.session_state.mock_current_q and st.session_state.mock_qnum == 1:
            if st.button("▶️ Start Mock Interview", use_container_width=True, type="primary"):
                with st.spinner("Generating first question..."):
                    q = call_ollama(prompt_mock_next([], interview_type, topic, 1))
                st.session_state.mock_current_q = q
                st.rerun()

        if st.session_state.mock_history:
            with st.expander(f"📜 Session so far ({len(st.session_state.mock_history)} answered)", expanded=False):
                for i, h in enumerate(st.session_state.mock_history):
                    st.markdown(f"**Q{i+1}:** {h['q']} | **Score:** {h['score']}/10")
                    st.divider()

        if st.session_state.mock_current_q:
            st.info(f"**Question {st.session_state.mock_qnum} of 5:**\n\n{st.session_state.mock_current_q}")
            mock_ans = st.text_area("💬 Your Answer", height=180, key="mock_ans_box",
                                    placeholder="Type your answer here...")

            if st.button("✅ Submit & Next Question", use_container_width=True, type="primary"):
                if not mock_ans.strip():
                    st.warning("Write an answer before submitting.")
                else:
                    with st.spinner("Evaluating..."):
                        feedback = call_ollama(prompt_evaluate(
                            st.session_state.mock_current_q, mock_ans, interview_type))
                    score = extract_score(feedback)
                    st.markdown("#### 📊 Feedback")
                    st.markdown(feedback)
                    st.metric("Score", f"{score}/10")

                    if st.session_state.user_id:
                        save_session(st.session_state.user_id, interview_type, topic,
                                     st.session_state.mock_current_q, mock_ans, score)

                    st.session_state.mock_history.append({
                        "q": st.session_state.mock_current_q,
                        "a": mock_ans, "score": score
                    })

                    if st.session_state.mock_qnum < 5:
                        st.session_state.mock_qnum += 1
                        with st.spinner("Loading next question..."):
                            nq = call_ollama(prompt_mock_next(
                                st.session_state.mock_history,
                                interview_type, topic,
                                st.session_state.mock_qnum))
                        st.session_state.mock_current_q = nq
                        st.rerun()
                    else:
                        scores = [h["score"] for h in st.session_state.mock_history]
                        avg    = round(sum(scores) / len(scores), 1)
                        st.success(f"🎉 Mock interview complete! Average score: **{avg}/10**")
                        st.session_state.mock_current_q = ""

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — EVALUATE ANSWER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "✍️ Evaluate Answer":
    st.markdown('<div class="nav-page-title">✍️ Answer Evaluator</div>', unsafe_allow_html=True)
    st.caption("Paste any question and your answer — get instant AI feedback and a score.")

    if VECTOR_DB and st.session_state.eval_prefill:
        st.info("📋 Question pre-filled from Question Bank")

    q_input = st.text_area("📌 Interview Question", height=100,
                            value=st.session_state.eval_prefill,
                            placeholder="Paste the interview question here...")
    a_input = st.text_area("💬 Your Answer", height=200,
                            placeholder="Type or paste your answer here...")

    if st.button("🔍 Evaluate My Answer", use_container_width=True, type="primary"):
        if not q_input.strip() or not a_input.strip():
            st.warning("⚠️ Provide both a question and your answer.")
        else:
            ph = st.empty(); full = ""
            st.markdown("### 📊 Evaluation Feedback")
            for chunk in call_ollama_stream(prompt_evaluate(q_input, a_input, interview_type)):
                full += chunk; ph.markdown(full + "▌")
            ph.markdown(full)
            score = extract_score(full)
            col1, col2, col3 = st.columns(3)
            col2.metric("⭐ Overall Score", f"{score}/10")

            if st.session_state.user_id:
                save_session(st.session_state.user_id, interview_type,
                             topic or "General", q_input, a_input, score)
                st.caption("✅ Saved to your profile.")
            st.session_state.eval_prefill = ""

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — HINTS MODE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Hints Mode":
    st.markdown('<div class="nav-page-title">💡 Progressive Hints</div>', unsafe_allow_html=True)
    st.caption("Get clues one at a time — bot reveals hints without giving the full answer.")

    hint_q = st.text_area("Paste your interview question", height=100,
                           placeholder="e.g. Explain the difference between REST and GraphQL")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Reset Hints"):
            st.session_state.hints = []; st.rerun()

    if hint_q and st.button("💡 Give me a hint", use_container_width=True, type="primary"):
        if len(st.session_state.hints) >= 5:
            st.warning("Maximum 5 hints reached. Reset to start again.")
        else:
            with st.spinner("Thinking of a hint..."):
                h = call_ollama(prompt_hint(hint_q, st.session_state.hints))
            st.session_state.hints.append(h)

    for h in st.session_state.hints:
        st.markdown(f'<div class="hint-box">💡 {h}</div>', unsafe_allow_html=True)

    if len(st.session_state.hints) >= 3:
        st.divider()
        if st.button("🎯 Show full model answer"):
            with st.spinner("Generating model answer..."):
                ans = call_ollama(f"Give a complete detailed model answer for: {hint_q}")
            st.markdown("### ✅ Model Answer")
            st.markdown(ans)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — FLASHCARDS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🃏 Flashcards":
    st.markdown('<div class="nav-page-title">🃏 Flashcard Quiz</div>', unsafe_allow_html=True)
    st.caption("Quick revision cards — flip to reveal the answer.")

    col1, col2 = st.columns([3, 1])
    with col1:
        ft = st.text_input("Topic for flashcards", placeholder="e.g. Python OOP, SQL, Recursion")
    with col2:
        n_cards = st.selectbox("Cards", [5, 8, 10, 15], index=1)

    if st.button("🃏 Generate Flashcards", use_container_width=True, type="primary"):
        if not ft:
            st.warning("Enter a topic.")
        else:
            with st.spinner("Generating flashcards..."):
                raw = call_ollama(prompt_flashcards(ft, interview_type, n_cards))
            cards = []
            for block in raw.split("---"):
                f, b = "", ""
                for line in block.strip().splitlines():
                    if line.startswith("FRONT:"): f = line.replace("FRONT:", "").strip()
                    elif line.startswith("BACK:"): b = line.replace("BACK:", "").strip()
                if f and b: cards.append({"front": f, "back": b})
            if cards:
                st.session_state.flashcards    = cards
                st.session_state.flash_idx     = 0
                st.session_state.flash_show_back = False
                st.success(f"✅ {len(cards)} flashcards generated!")
            else:
                st.warning("Could not parse flashcards. Try again.")

    if st.session_state.flashcards:
        cards = st.session_state.flashcards
        idx   = st.session_state.flash_idx
        total = len(cards)
        card  = cards[idx]

        st.markdown(f"**Card {idx+1} of {total}**")
        st.progress((idx + 1) / total)

        if st.session_state.flash_show_back:
            st.markdown(f'<div class="flash-back">💡 <b>Answer</b><br><br>{card["back"]}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="flash-front">❓ <b>Question</b><br><br>{card["front"]}</div>',
                        unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("⬅️ Prev") and idx > 0:
                st.session_state.flash_idx -= 1; st.session_state.flash_show_back = False; st.rerun()
        with c2:
            if st.button("🔄 Flip"):
                st.session_state.flash_show_back = not st.session_state.flash_show_back; st.rerun()
        with c3:
            if st.button("➡️ Next") and idx < total - 1:
                st.session_state.flash_idx += 1; st.session_state.flash_show_back = False; st.rerun()
        with c4:
            if st.button("🔁 Restart"):
                st.session_state.flash_idx = 0; st.session_state.flash_show_back = False; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — JD ANALYZER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📄 JD Analyzer":
    st.markdown('<div class="nav-page-title">📄 Job Description Analyzer</div>', unsafe_allow_html=True)
    st.caption("Paste any job posting — get extracted skills and targeted questions.")

    jd_text = st.text_area("Paste Job Description here", height=260,
                            placeholder="Copy-paste any job posting here...")

    if st.button("🔍 Analyze JD", use_container_width=True, type="primary"):
        if not jd_text.strip():
            st.warning("⚠️ Paste a job description first.")
        else:
            result = stream_response(prompt_jd(jd_text), "🎯 JD Analysis & Targeted Questions")
            st.session_state.jd_result = result

    if st.session_state.jd_result:
        st.divider()
        pdf_download_btn("JD Analysis", st.session_state.jd_result, "jd_analysis.pdf")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — RESUME QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📑 Resume Questions":
    st.markdown('<div class="nav-page-title">📑 Resume-Based Questions</div>', unsafe_allow_html=True)
    st.caption("Upload your resume — get questions tailored to YOUR background.")

    resume_file = st.file_uploader("Upload resume (TXT or PDF)", type=["txt", "pdf"])
    resume_text = ""

    if resume_file:
        if resume_file.name.endswith(".txt"):
            resume_text = resume_file.read().decode("utf-8", errors="ignore")
        elif resume_file.name.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(resume_file)
                resume_text = " ".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                st.error("Run: pip install PyPDF2")

        if resume_text:
            st.success(f"✅ Resume loaded ({len(resume_text)} characters)")
            with st.expander("Preview resume text"):
                st.text(resume_text[:1000] + ("..." if len(resume_text) > 1000 else ""))

            if st.button("🎯 Generate Resume-Based Questions", use_container_width=True, type="primary"):
                stream_response(prompt_resume(resume_text, interview_type),
                                "📌 Personalized Interview Questions")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 8 — COMPANY PREP
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏢 Company Prep":
    st.markdown('<div class="nav-page-title">🏢 Company-Specific Prep</div>', unsafe_allow_html=True)
    st.caption("Get questions tailored to your target company's interview style.")

    if company == "None (General)":
        st.warning("⚠️ Select a target company from the sidebar first.")
    else:
        st.markdown(f'<span class="company-badge">🏢 {company}</span>', unsafe_allow_html=True)
        role_input = st.text_input("Role you are applying for",
                                   placeholder="e.g. SDE-2, Data Scientist, PM")

        if st.button(f"🎯 Generate {company} Questions", use_container_width=True, type="primary"):
            if not role_input.strip():
                st.warning("⚠️ Enter the role you are applying for.")
            else:
                result = stream_response(prompt_company(company, role_input, experience),
                                         f"📌 {company} Interview Prep")
                st.session_state.company_result = result

        if st.session_state.company_result:
            st.divider()
            pdf_download_btn(f"{company} Prep", st.session_state.company_result,
                             f"{company.lower().replace(' ','_')}_prep.pdf")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 9 — STUDY ROADMAP
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗺️ Study Roadmap":
    st.markdown('<div class="nav-page-title">🗺️ Personalized Study Roadmap</div>', unsafe_allow_html=True)
    st.caption("Get a week-by-week prep plan tailored to your role and timeline.")

    col1, col2 = st.columns(2)
    with col1:
        role_rm  = st.text_input("Target Role", placeholder="e.g. Data Scientist, Backend SDE")
    with col2:
        timeline = st.selectbox("Preparation Time",
                                ["1 week", "2 weeks", "1 month", "3 months"])

    if st.button("📍 Generate My Roadmap", use_container_width=True, type="primary"):
        if not role_rm.strip():
            st.warning("⚠️ Enter your target role.")
        else:
            result = stream_response(
                prompt_roadmap(role_rm, experience, timeline, company),
                "🗺️ Your Study Roadmap")
            st.session_state.roadmap_result = result

    if st.session_state.roadmap_result:
        st.divider()
        pdf_download_btn("Study Roadmap", st.session_state.roadmap_result, "study_roadmap.pdf")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 10 — SCORE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Score Dashboard":
    st.markdown('<div class="nav-page-title">📊 Score Dashboard</div>', unsafe_allow_html=True)

    if not st.session_state.user_id:
        st.warning("⚠️ Please log in from the sidebar to see your dashboard.")
    else:
        sessions = get_user_sessions(st.session_state.user_id)

        if not sessions:
            st.info("No sessions saved yet. Complete some evaluations or mock interviews first!")
        else:
            scores = [s[4] for s in sessions if s[4] is not None]
            avg    = round(sum(scores) / len(scores), 1) if scores else 0
            best   = max(scores) if scores else 0
            week_count = sum(1 for s in sessions
                             if s[5][:10] >= (datetime.datetime.now() -
                                              datetime.timedelta(days=7)).strftime("%Y-%m-%d"))

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📋 Total Sessions", len(sessions))
            c2.metric("⭐ Average Score",  f"{avg}/10")
            c3.metric("🏆 Best Score",     f"{best}/10")
            c4.metric("📅 This Week",      week_count)

            st.divider()
            st.markdown("#### 📈 Score Over Time")
            df = pd.DataFrame(sessions, columns=["Type","Topic","Question","Answer","Score","Date"])
            df["Date"]  = pd.to_datetime(df["Date"])
            df["Score"] = pd.to_numeric(df["Score"], errors="coerce")
            df_chart    = df.set_index("Date")[["Score"]].dropna()
            if not df_chart.empty:
                st.line_chart(df_chart)

            st.markdown("#### 📊 Performance by Interview Type")
            type_avg = df.groupby("Type")["Score"].mean().round(1)
            if not type_avg.empty:
                st.bar_chart(type_avg)

            st.divider()
            st.markdown("#### 📋 Recent Sessions")
            for row in sessions[:15]:
                itype, itopic, iq, ia, iscore, idate = row
                color = "🟢" if iscore >= 7 else "🟡" if iscore >= 5 else "🔴"
                with st.expander(f"{color} {itype} | {itopic} | {iscore}/10 | {idate[:10]}"):
                    st.markdown(f"**Q:** {iq}")
                    st.markdown(f"**A:** {ia}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 11 — TIMED MODE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⏱️ Timed Mode":
    st.markdown('<div class="nav-page-title">⏱️ Timed Answer Mode</div>', unsafe_allow_html=True)
    st.caption("Simulate real interview pressure with a countdown timer.")

    timer_mins = st.slider("Time limit per question (minutes)", 1, 5, 2)
    st.session_state.timer_limit = timer_mins * 60

    if not topic:
        st.warning("⚠️ Set a topic in the sidebar first.")
    else:
        if st.button("🎯 Get Question & Start Timer", use_container_width=True, type="primary"):
            with st.spinner("Generating question..."):
                q = call_ollama(prompt_questions(interview_type, topic, difficulty, experience, company))
            st.session_state.timed_question  = q
            st.session_state.timer_start     = time.time()
            st.session_state.timer_running   = True
            st.session_state.timed_submitted = False
            st.rerun()

        if st.session_state.timed_question:
            st.info(st.session_state.timed_question)

            if st.session_state.timer_running and not st.session_state.timed_submitted:
                elapsed   = int(time.time() - st.session_state.timer_start)
                remaining = st.session_state.timer_limit - elapsed
                if remaining <= 0:
                    st.error("⏰ Time's up!")
                    st.session_state.timer_running = False
                else:
                    mins, secs = divmod(remaining, 60)
                    css = "timer-red" if remaining < 30 else "timer-green"
                    st.markdown(f'<div class="{css}">{mins:02d}:{secs:02d}</div>',
                                unsafe_allow_html=True)
                    st.progress(remaining / st.session_state.timer_limit)
                    time.sleep(1); st.rerun()

            timed_ans = st.text_area("💬 Your Answer", height=180, key="timed_ans_input",
                                     placeholder="Type your answer here...")

            if st.button("✅ Submit Answer", use_container_width=True,
                         disabled=st.session_state.timed_submitted):
                st.session_state.timer_running   = False
                st.session_state.timed_submitted = True
                elapsed = int(time.time() - st.session_state.timer_start)
                st.success(f"✅ Submitted in {elapsed} seconds!")

                with st.spinner("Evaluating..."):
                    feedback = call_ollama(prompt_evaluate(
                        st.session_state.timed_question, timed_ans, interview_type))

                st.markdown("### 📊 Feedback")
                st.markdown(feedback)
                score = extract_score(feedback)
                st.metric("⭐ Score", f"{score}/10")

                if st.session_state.user_id:
                    save_session(st.session_state.user_id, interview_type, topic,
                                 st.session_state.timed_question, timed_ans, score)
                    st.caption("✅ Saved to your profile.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 12 — QUESTION BANK (Vector DB)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧠 Question Bank":
    st.markdown('<div class="nav-page-title">🧠 Question Bank</div>', unsafe_allow_html=True)
    st.caption("Browse and search all questions stored by the AI using semantic search.")

    if not VECTOR_DB:
        st.error("Vector DB not installed. Run: `pip install chromadb sentence-transformers`")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Questions", total_questions_all())
        c2.metric("This Interview Type", count_questions(interview_type))
        c3.metric("Interview Type", interview_type.split("/")[0])

        st.divider()
        st.markdown("#### 🔍 Semantic Search")
        st.caption("Search finds similar questions even with different wording.")
        search_q = st.text_input("Search question bank",
                                 placeholder="e.g. binary search, system design, leadership")
        n_res = st.slider("Number of results", 1, 10, 5)

        if st.button("🔍 Search", use_container_width=True, type="primary"):
            if not search_q.strip():
                st.warning("Enter a search term.")
            else:
                with st.spinner("Searching vector database..."):
                    results = search_similar(interview_type, search_q, n_results=n_res)
                if not results:
                    st.info("No questions found. Generate some questions first!")
                else:
                    st.markdown(f"**Found {len(results)} similar questions:**")
                    for i, (doc, meta) in enumerate(results):
                        with st.expander(
                            f"Result {i+1} — Topic: {meta.get('topic','')} | "
                            f"{meta.get('difficulty','')} | {meta.get('experience','')}"):
                            st.markdown(doc)
                            col_a, col_b = st.columns(2)
                            with col_a:
                                if st.button(f"✍️ Use in Evaluator", key=f"use_{i}"):
                                    st.session_state.eval_prefill = doc
                                    st.success("Copied to Evaluate Answer page!")
                            with col_b:
                                if st.button(f"📥 Export this", key=f"exp_{i}"):
                                    pdf_download_btn("Question", doc, f"question_{i+1}.pdf")

        st.divider()
        st.markdown("#### 📋 Browse All Questions")
        filter_topic = st.text_input("Filter by topic (optional)",
                                     placeholder="e.g. Python, SQL, Recursion")

        all_qs = get_all_questions(
            interview_type,
            topic=filter_topic.strip() if filter_topic.strip() else None
        )

        if not all_qs:
            st.info("No questions stored yet for this interview type. "
                    "Go to Generate Questions and generate some!")
        else:
            st.caption(f"Showing {len(all_qs)} question(s) for **{interview_type}**")
            for i, (doc, meta) in enumerate(all_qs):
                color = "🟦"
                diff  = meta.get("difficulty", "")
                if diff == "Advanced": color = "🟥"
                elif diff == "Intermediate": color = "🟨"
                elif diff == "Beginner": color = "🟩"

                with st.expander(
                    f"{color} Q{i+1} — {meta.get('topic','')} | "
                    f"{diff} | {meta.get('experience','')}"):
                    st.markdown(doc)
                    if st.button(f"✍️ Send to Evaluator", key=f"browse_{i}"):
                        st.session_state.eval_prefill = doc
                        st.success("✅ Copied! Go to Evaluate Answer page.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 13 — EXPORT PDF
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📥 Export PDF":
    st.markdown('<div class="nav-page-title">📥 Export to PDF</div>', unsafe_allow_html=True)
    st.caption("Download any generated content as a PDF file.")

    export_choice = st.selectbox("What to export", [
        "Last generated questions",
        "Study roadmap",
        "JD analysis",
        "Company prep",
        "Full session history",
    ])

    content_map = {
        "Last generated questions": ("Interview Questions", st.session_state.last_q_block,    "questions.pdf"),
        "Study roadmap":            ("Study Roadmap",       st.session_state.roadmap_result,   "roadmap.pdf"),
        "JD analysis":              ("JD Analysis",         st.session_state.jd_result,         "jd_analysis.pdf"),
        "Company prep":             ("Company Prep",        st.session_state.company_result,    "company_prep.pdf"),
    }

    if export_choice == "Full session history":
        if not st.session_state.user_id:
            st.warning("⚠️ Log in from the sidebar first.")
        else:
            sessions = get_user_sessions(st.session_state.user_id)
            if not sessions:
                st.info("No sessions to export yet.")
            else:
                hist_text = f"Interview History — {st.session_state.username}\n{'='*50}\n\n"
                for i, s in enumerate(sessions):
                    hist_text += (f"Session {i+1}\nType:  {s[0]}\nTopic: {s[1]}\n"
                                  f"Q: {s[2]}\nA: {s[3]}\nScore: {s[4]}/10\nDate: {s[5][:10]}\n"
                                  f"{'-'*40}\n\n")
                st.text_area("Preview", hist_text[:2000], height=200)
                pdf_download_btn("Session History", hist_text, "session_history.pdf")
    else:
        title, content, filename = content_map[export_choice]
        if not content:
            st.info(f"⚠️ Generate '{export_choice}' first from its page.")
        else:
            st.text_area("Preview", content[:2000] + ("..." if len(content) > 2000 else ""),
                         height=200)
            pdf_download_btn(title, content, filename)
