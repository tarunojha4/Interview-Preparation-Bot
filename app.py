import os
import sqlite3
import datetime
import base64
import re

import pandas as pd
import streamlit as st
from fpdf import FPDF
from groq import Groq

st.set_page_config(page_title="Interview Prep Bot", page_icon="🎯", layout="wide")

# Ephemeral storage on Streamlit Cloud; local file otherwise.
DB_PATH = os.environ.get(
    "DB_PATH",
    "/tmp/interview_bot.db" if os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud" else "interview_bot.db",
)

# ── INTEGRATED VECTOR STORE FUNCTIONS (SQLite Backup Mode with Auto-Seeding) ──
VECTOR_DB = True

def init_vector_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS question_bank(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        interview_type TEXT,
        topic TEXT,
        content TEXT,
        difficulty TEXT,
        experience TEXT,
        created_at TEXT)""")
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM question_bank WHERE interview_type='Data Science / ML'")
    count = c.fetchone()[0]
    
    if count < 50:
        ds_questions = [
            ("What is the difference between Supervised and Unsupervised Learning?", "Machine Learning", "Beginner"),
            ("Explain Bias-Variance Tradeoff and how it affects model performance.", "Machine Learning", "Intermediate"),
            ("What is Overfitting and how can you prevent it in Tree-based models?", "Machine Learning", "Intermediate"),
            ("Explain the difference between L1 (Lasso) and L2 (Ridge) Regularization.", "Machine Learning", "Advanced"),
            ("How does a Decision Tree decide where to split a node?", "Machine Learning", "Intermediate"),
            ("What is Random Forest and how does Ensemble learning work?", "Machine Learning", "Intermediate"),
            ("Explain Gradient Boosting and how it differs from Bagging.", "Machine Learning", "Advanced"),
            ("What are XGBoost's primary advantages over standard GBM?", "Machine Learning", "Advanced"),
            ("How does Logistic Regression compute probabilities dynamically?", "Machine Learning", "Intermediate"),
            ("What is the Support Vector Machine (SVM) kernel trick?", "Machine Learning", "Advanced"),
            ("Explain K-Means Clustering and how you find the optimal 'K' value.", "Machine Learning", "Beginner"),
            ("What is Hierarchical Clustering and dendrogram evaluation?", "Machine Learning", "Intermediate"),
            ("Explain Principal Component Analysis (PCA) step-by-step.", "Data Science", "Advanced"),
            ("What is t-SNE and when do you use it over PCA?", "Data Science", "Advanced"),
            ("What are Confusion Matrix, Precision, Recall, and F1-Score?", "Data Science", "Beginner"),
            ("Explain ROC-AUC score and when it can fail for imbalanced datasets.", "Data Science", "Intermediate"),
            ("How do you handle highly imbalanced datasets in classification tasks?", "Data Science", "Intermediate"),
            ("What is the difference between Mean Absolute Error (MAE) and MSE?", "Data Science", "Beginner"),
            ("Explain Root Mean Squared Logarithmic Error (RMSLE) usage.", "Data Science", "Intermediate"),
            ("What is Cross-Validation and why is Stratified K-Fold used?", "Data Science", "Beginner"),
            ("How do you detect and handle outliers in a dataset?", "Data Science", "Intermediate"),
            ("What is Data Normalization vs Standardization? When to use which?", "Data Science", "Beginner"),
            ("Explain Missing Value Imputation strategies for data streams.", "Data Science", "Intermediate"),
            ("What is One-Hot Encoding vs Label Encoding?", "Data Science", "Beginner"),
            ("Explain the concept of Feature Selection vs Feature Extraction.", "Data Science", "Intermediate"),
            ("What is the Central Limit Theorem and why does it matter?", "Data Science", "Beginner"),
            ("Explain p-value, Type I error, and Type II error in statistics.", "Data Science", "Intermediate"),
            ("What is A/B Testing and how do you calculate sample size?", "Data Science", "Advanced"),
            ("Explain the difference between Correlation and Causation.", "Data Science", "Beginner"),
            ("What is Bayes' Theorem and how is it used in Naive Bayes?", "Machine Learning", "Beginner"),
            ("Explain the architecture of a basic Artificial Neural Network (ANN).", "Deep Learning", "Intermediate"),
            ("What is Backpropagation and how do weights update via SGD?", "Deep Learning", "Intermediate"),
            ("What is the Vanishing/Exploding Gradient problem in Deep Networks?", "Deep Learning", "Advanced"),
            ("Why is ReLU preferred over Sigmoid/Tanh hidden layer activations?", "Deep Learning", "Intermediate"),
            ("What is Dropout Regularization and how does it work during test time?", "Deep Learning", "Intermediate"),
            ("Explain Convolutional Neural Networks (CNNs) and pooling mechanics.", "Deep Learning", "Intermediate"),
            ("What are Recurrent Neural Networks (RNNs) and how do LSTMs fix them?", "Deep Learning", "Advanced"),
            ("Explain the core architecture of the Transformer model.", "Deep Learning", "Advanced"),
            ("What is Self-Attention and multi-head attention processing?", "Deep Learning", "Advanced"),
            ("What is the difference between BERT and GPT architectures?", "Deep Learning", "Advanced"),
            ("Explain Tokenization, Lemmatization, and Stemming in NLP pipelines.", "NLP", "Beginner"),
            ("What is TF-IDF and what are its limitations?", "NLP", "Beginner"),
            ("Explain Word2Vec, Skip-gram, and Continuous Bag of Words (CBOW).", "NLP", "Intermediate"),
            ("What is Cosine Similarity and how is it used in search engines?", "Data Science", "Beginner"),
            ("Explain the concept of Transfer Learning with practical examples.", "Deep Learning", "Intermediate"),
            ("What are Generative Adversarial Networks (GANs) and how do they train?", "Deep Learning", "Advanced"),
            ("Explain Reinforcement Learning, Markov Decision Processes, and Q-Learning.", "Machine Learning", "Advanced"),
            ("What is Data Leakage and how can you detect it during training?", "Data Science", "Intermediate"),
            ("Explain Time Series Stationarity and the Augmented Dickey-Fuller test.", "Data Science", "Advanced"),
            ("What is the difference between ARIMA and LSTM for forecasting?", "Data Science", "Advanced")
        ]
        
        now_str = datetime.datetime.now().isoformat()
        for q, top, diff in ds_questions:
            content_block = f"Question: {q}\n\nTarget Guidance:\n1. Core Definitions\n2. Practical Implementation Context\n3. Mathematical Underpinnings"
            c.execute("""INSERT INTO question_bank(interview_type, topic, content, difficulty, experience, created_at)
                         VALUES(?,?,?,?,?,?)""", 
                      ("Data Science / ML", top.lower(), content_block, diff, "Junior (1-3 yrs)", now_str))
        conn.commit()
    conn.close()

def save_question(interview_type, topic, content, difficulty, experience):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO question_bank(interview_type, topic, content, difficulty, experience, created_at)
                 VALUES(?,?,?,?,?,?)""", 
              (interview_type, topic.lower(), content, difficulty, experience, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def search_similar(interview_type, search_term, n_results=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT content, topic, difficulty, experience FROM question_bank 
                 WHERE interview_type=? AND (topic LIKE ? OR content LIKE ?) 
                 ORDER BY id DESC LIMIT ?""", 
              (interview_type, f"%{search_term.lower()}%", f"%{search_term.lower()}%", n_results))
    rows = c.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append((r[0], {"topic": r[1], "difficulty": r[2], "experience": r[3]}))
    return results

def count_questions(interview_type):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM question_bank WHERE interview_type=?", (interview_type,))
    count = c.fetchone()[0]
    conn.close()
    return count

def total_questions_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM question_bank")
    count = c.fetchone()[0]
    conn.close()
    return count

GROQ_MODEL = "llama-3.1-8b-instant"

def _init_groq_client():
    if "groq_client" not in st.session_state:
        st.session_state.groq_client = None
    if st.session_state.groq_client is None and "GROQ_API_KEY" in st.secrets:
        st.session_state.groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

_init_groq_client()
client = st.session_state.groq_client
GROQ_READY = client is not None

INTERVIEW_TYPES   = ["Software Engineering / Coding", "Data Science / ML", "System Design", "HR / Behavioral"]
DIFFICULTY_LEVELS = ["Beginner", "Intermediate", "Advanced"]
EXPERIENCE_LEVELS = ["Fresher (0-1 yr)", "Junior (1-3 yrs)", "Mid (3-5 yrs)", "Senior (5+ yrs)"]
COMPANIES         = ["None (General)", "Google", "Amazon", "Microsoft", "Meta", "Netflix", "Apple", "Flipkart", "Infosys", "TCS", "Wipro"]

st.markdown("""
<style>
.main-header{font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stButton>button{border-radius:8px;font-weight:500}
.hint-box{background:#fffbea;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:0 8px 8px 0;margin:8px 0;font-size:.95rem}
.flash-front{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-radius:16px;padding:2rem;text-align:center;min-height:180px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:500;margin:10px 0}
.flash-back{background:linear-gradient(135deg,#11998e,#38ef7d);color:white;border-radius:16px;padding:2rem;text-align:center;min-height:180px;display:flex;align-items:center;justify-content:center;font-size:1rem;margin:10px 0}
.company-badge{background:#e0e7ff;color:#3730a3;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;display:inline-block;margin-bottom:12px}
.nav-page-title{font-size:1.6rem;font-weight:700;margin-bottom:.4rem;color:#1e293b}
div[data-testid="stSidebar"]{background:#f8faff}
</style>
""", unsafe_allow_html=True)

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
    conn.commit()
    conn.close()
    init_vector_db()

def get_or_create_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=?", (username,))
    row = c.fetchone()
    if row: conn.close(); return row[0]
    c.execute("INSERT INTO users(username,created_at) VALUES(?,?)",
              (username, datetime.datetime.now().isoformat()))
    conn.commit()
    uid = c.lastrowid
    conn.close()
    return uid

def save_session(user_id, interview_type, topic, question, answer, score):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO sessions(user_id,interview_type,topic,question,answer,score,created_at)
                 VALUES(?,?,?,?,?,?,?)""",
              (user_id, interview_type, topic, question, answer, score,
               datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_sessions(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT interview_type,topic,question,answer,score,created_at
                 FROM sessions WHERE user_id=? ORDER BY created_at DESC""", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def call_ollama(prompt):
    if not GROQ_READY: return "❌ Groq API Key missing!"
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=2048
        )
        return completion.choices[0].message.content.strip()
    except Exception as e: return f"❌ Error: {str(e)}"

def call_ollama_stream(prompt):
    if not GROQ_READY:
        yield "❌ Groq API Key missing!"
        return
    try:
        stream = client.chat.completions.create(
            model=GROQ_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=3000, stream=True
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content: yield content
    except Exception as e: yield f"❌ Stream Pipeline Error: {str(e)}"

# ── UPGRADED PROMPTS TO GENERATE EXACTLY 10 QUESTIONS ──────────────────────────
def prompt_questions(interview_type, topic, difficulty, experience, company):
    cn = f" tailored for {company} interview style" if company != "None (General)" else ""
    return f"""You are an expert technical interviewer{cn}.
Generate EXACTLY 10 distinct, highly strategic {difficulty} level interview questions for a {experience} candidate specializing in: {topic} (Under category: {interview_type}).

Provide the output strictly in this structured format for all 10 questions:
Q1: [Question Statement]
Guidance: [Brief 1-2 sentence pointers on what the interviewer expects in an ideal answer]

... up to Q10. Ensure the questions test core concepts, practical deployment, and theoretical depth without repetitions."""

def prompt_evaluate(question, answer, interview_type):
    return f"""You are a strict but fair {interview_type} interviewer evaluating a candidate.
Question: {question}
Candidate Answer: {answer}
Evaluate on scaling dimensions out of 10. Start your response with: SCORE: X/10"""

def prompt_roadmap(role, experience, timeline, company):
    cn = f" targeting {company}" if company != "None (General)" else ""
    return f"""Create a detailed roadmap for a {experience} {role}{cn} with {timeline} to prepare."""

def prompt_jd(jd):
    return f"""Analyze this job description and extract core questions:\n{jd}"""

def prompt_resume(resume, interview_type):
    return f"""Based on this resume, generate personalized {interview_type} questions:\n{resume}"""

def prompt_mock_next(history, interview_type, topic, qnum):
    hist = "\n".join([f"Q{i+1}: {h['q']}\nA: {h['a']}" for i, h in enumerate(history)])
    return f"""You are conducting a {interview_type} mock interview on: {topic}. Previous history:\n{hist}\nAsk ONLY question {qnum} out of 5."""

def prompt_hint(question, hints):
    return f"""Give a subtle hint for: "{question}". Existing hints: {hints}"""

def prompt_flashcards(topic, interview_type, n=8):
    return f"""Generate {n} flashcards for {interview_type} on: {topic}.\nFormat:\nFRONT: [text]\nBACK: [text]\n---"""

def prompt_company(company, role, experience):
    return f"""Generate 5 targeted questions asked at {company} for {role} ({experience})."""

def extract_score(text):
    m = re.search(r"SCORE:\s*(\d+)", text)
    return int(m.group(1)) if m else 0

def generate_pdf(title, content):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Arial", size=10)
    pdf.ln(4)
    for line in content.split("\n"):
        safe = line.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe)
    return pdf.output(dest="S").encode("latin-1")

def pdf_download_btn(title, content, filename):
    if not content: st.info("No content to export."); return
    b64 = base64.b64encode(generate_pdf(title, content)).decode()
    st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="{filename}" style="display:inline-block;padding:8px 20px;background:#6366f1;color:white;border-radius:8px;text-decoration:none;font-weight:600;">📥 Download PDF</a>', unsafe_allow_html=True)

def stream_response(prompt, header=None):
    if header: st.markdown(f"### {header}")
    ph = st.empty()
    full = ""
    for chunk in call_ollama_stream(prompt):
        full += chunk
        ph.markdown(full + "▌")
    ph.markdown(full)
    return full

# ── INIT STATES ───────────────────────────────────────────────────────────────
init_db()
defaults = {
    "username": "", "user_id": None, "mock_history": [], "mock_qnum": 1, "mock_current_q": "", "hints": [],
    "flash_idx": 0, "flash_show_back": False, "flashcards": [], "timer_running": False, "timer_start": 0, "timer_limit": 120,
    "timed_question": "", "timed_submitted": False, "last_q_block": "", "roadmap_result": "", "jd_result": "", "company_result": "", "eval_prefill": ""
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

st.markdown('<div class="main-header">🎯 Interview Preparation Bot</div>', unsafe_allow_html=True)
st.markdown("*Powered by Groq Cloud + LLaMA 3.1 Architecture — Your Private AI Coach*")

# ── SIDEBAR SELECTION PANEL ───────────────────────────────────────────────────
with st.sidebar:
    if not GROQ_READY:
        api_key = st.text_input("Groq API Key", type="password", help="Required for AI features. Add GROQ_API_KEY in Streamlit Cloud secrets to skip this.")
        if api_key:
            st.session_state.groq_client = Groq(api_key=api_key)
            st.rerun()

    st.markdown("## 👤 User Profile")
    uname = st.text_input("Your name", value=st.session_state.username)
    if st.button("🔐 Login / Switch", use_container_width=True):
        if uname.strip():
            st.session_state.username = uname.strip()
            st.session_state.user_id  = get_or_create_user(uname.strip())
    if st.session_state.user_id: st.info(f"Active: **{st.session_state.username}**")

    st.divider()
    st.markdown("## ⚙️ Settings")
    experience     = st.selectbox("Experience Level", EXPERIENCE_LEVELS)
    interview_type = st.selectbox("Interview Type",   INTERVIEW_TYPES)
    difficulty     = st.selectbox("Difficulty",       DIFFICULTY_LEVELS)
    topic          = st.text_input("Topic / Role", placeholder="e.g. Machine Learning")
    company        = st.selectbox("Target Company",   COMPANIES)

    st.divider()
    pages = ["📋 Generate Questions", "🎭 Mock Interview", "✍️ Evaluate Answer", "💡 Hints Mode", "🃏 Flashcards", "📄 JD Analyzer", "📑 Resume Questions", "🏢 Company Prep", "🗺️ Study Roadmap", "📊 Score Dashboard", "⏱️ Timed Mode", "🧠 Browse System Bank", "📥 Export PDF"]
    page = st.radio("Navigate Actions", pages, label_visibility="collapsed")

# ── ACTIONS INTEGRATION ROUTER ────────────────────────────────────────────────
if page == "📋 Generate Questions":
    st.markdown('<div class="nav-page-title">📋 10-Question Generator Pipeline</div>', unsafe_allow_html=True)
    st.caption("This action uses Groq LLaMA 3.1 to generate exactly 10 comprehensive distinct conceptual questions.")
    
    if st.button("🚀 Generate 10 Questions", use_container_width=True, type="primary"):
        if not topic:
            st.warning("⚠️ Please enter a topic in the sidebar setup panel.")
        else:
            prompt = prompt_questions(interview_type, topic, difficulty, experience, company)
            result = stream_response(prompt, f"📌 Top 10 {topic} Interview Questions")
            st.session_state.last_q_block = result
            save_question(interview_type, topic, result, difficulty, experience)

    if st.session_state.last_q_block:
        st.divider()
        pdf_download_btn("10 Interview Questions Log", st.session_state.last_q_block, "top_10_questions.pdf")

elif page == "🎭 Mock Interview":
    st.markdown('<div class="nav-page-title">🎭 Mock Interview Mode</div>', unsafe_allow_html=True)
    if not topic: st.warning("⚠️ Set a specific target topic in the sidebar configuration.")
    else:
        if not st.session_state.mock_current_q and st.session_state.mock_qnum == 1:
            if st.button("▶️ Start Mock Interview Session", use_container_width=True, type="primary"):
                st.session_state.mock_current_q = call_ollama(prompt_mock_next([], interview_type, topic, 1))
                st.rerun()
        if st.session_state.mock_current_q:
            st.info(f"**Question {st.session_state.mock_qnum} of 5:**\n\n{st.session_state.mock_current_q}")
            mock_ans = st.text_area("💬 Answer Prompt Area", height=150)
            if st.button("✅ Submit Prompt & Advance", use_container_width=True, type="primary"):
                feedback = call_ollama(prompt_evaluate(st.session_state.mock_current_q, mock_ans, interview_type))
                score = extract_score(feedback)
                st.markdown(feedback)
                st.session_state.mock_history.append({"q": st.session_state.mock_current_q, "score": score})
                if st.session_state.mock_qnum < 5:
                    st.session_state.mock_qnum += 1
                    st.session_state.mock_current_q = call_ollama(prompt_mock_next(st.session_state.mock_history, interview_type, topic, st.session_state.mock_qnum))
                    st.rerun()
                else:
                    st.success("🎉 Mock Interview Complete!")
                    st.session_state.mock_current_q = ""

elif page == "✍️ Evaluate Answer":
    st.markdown('<div class="nav-page-title">✍️ Answer Evaluator Engine</div>', unsafe_allow_html=True)
    q_input = st.text_area("📌 Target Question Context", value=st.session_state.eval_prefill)
    a_input = st.text_area("💬 Candidate Answer Input Field")
    if st.button("🔍 Run Quality Evaluation", use_container_width=True, type="primary"):
        full = stream_response(prompt_evaluate(q_input, a_input, interview_type), "### 📊 Quality Reports")

elif page == "💡 Hints Mode":
    st.markdown('<div class="nav-page-title">💡 Progressive Clue Engines</div>', unsafe_allow_html=True)
    hint_q = st.text_area("Question context mapping")
    if hint_q and st.button("💡 Extract Progressive Hint"):
        h = call_ollama(prompt_hint(hint_q, st.session_state.hints))
        st.session_state.hints.append(h)
    for h in st.session_state.hints: st.markdown(f'- {h}')

elif page == "🃏 Flashcards":
    st.markdown('<div class="nav-page-title">🃏 Revision Cards Dashboard</div>', unsafe_allow_html=True)
    ft = st.text_input("Target domain metrics mapping")
    if st.button("🃏 Run Flashcards Generator Pipeline"):
        raw = call_ollama(prompt_flashcards(ft, interview_type, 5))
        st.session_state.flashcards = [{"front": "Concept Card", "back": raw}]
    if st.session_state.flashcards:
        st.info(st.session_state.flashcards[0]["back"])

elif page == "📄 JD Analyzer":
    st.markdown('<div class="nav-page-title">📄 Job Description Parser</div>', unsafe_allow_html=True)
    jd_text = st.text_area("Paste Job Description raw text logs")
    if st.button("🔍 Core Processing Analytics Execution", type="primary"):
        st.session_state.jd_result = stream_response(prompt_jd(jd_text), "🎯 Target Profiles Metrics Extraction")

elif page == "📑 Resume Questions":
    st.markdown('<div class="nav-page-title">📑 Profile Vectors Mapping Round</div>', unsafe_allow_html=True)
    resume_file = st.file_uploader("Upload Profile text file logs", type=["txt"])
    if resume_file:
        r_text = resume_file.read().decode("utf-8")
        if st.button("🎯 Trigger Prompt Execution"): stream_response(prompt_resume(r_text, interview_type))

elif page == "🏢 Company Prep":
    st.markdown('<div class="nav-page-title">🏢 Enterprise Specific Structural Alignment</div>', unsafe_allow_html=True)
    role_input = st.text_input("Enter operational designation mapping target")
    if st.button(f"🎯 Compile Targeted {company} Framework"):
        st.session_state.company_result = stream_response(prompt_company(company, role_input, experience))

elif page == "🗺️ Study Roadmap":
    st.markdown('<div class="nav-page-title">🗺️ Strategic Route Maps Progression</div>', unsafe_allow_html=True)
    role_rm = st.text_input("Strategic target objective mapping")
    if st.button("📍 Compute Optimised Route Strategy"):
        st.session_state.roadmap_result = stream_response(prompt_roadmap(role_rm, experience, "1 month", company))

elif page == "📊 Score Dashboard":
    st.markdown('<div class="nav-page-title">📊 Metrics Performance Registries Center</div>', unsafe_allow_html=True)
    if st.session_state.user_id:
        sessions = get_user_sessions(st.session_state.user_id)
        st.write(pd.DataFrame(sessions, columns=["Type","Topic","Question","Answer","Score","Date"]))

elif page == "⏱️ Timed Mode":
    st.markdown('<div class="nav-page-title">⏱️ Temporal Constraint Assessment Sandbox</div>', unsafe_allow_html=True)
    if st.button("🎯 Inject Temporal Question Sequence"):
        st.session_state.timed_question = call_ollama(prompt_questions(interview_type, topic or "General", difficulty, experience, company))
    if st.session_state.timed_question: st.info(st.session_state.timed_question)

elif page == "🧠 Browse System Bank":
    st.markdown('<div class="nav-page-title">🧠 Central Registry Question Explorer</div>', unsafe_allow_html=True)
    search_q = st.text_input("Search keywords inside the 50-preloaded bank (e.g. SVM, Overfitting)")
    sel_type = st.selectbox("Domain type selector", ["Data Science / ML", "Software Engineering / Coding"])
    if st.button("Run System Bank Search Lookup", type="primary") or search_q:
        results = search_similar(sel_type, search_q, n_results=10)
        for doc, meta in results:
            with st.expander(f"📝 Topic Index: {meta.get('topic','').upper()}"):
                st.markdown(doc)
                if st.button("Inject into Evaluation Buffer", key=doc[:30]):
                    st.session_state.eval_prefill = doc

elif page == "📥 Export PDF":
    st.markdown('<div class="nav-page-title">📥 Output Report Generation Pipeline</div>', unsafe_allow_html=True)
    pdf_download_btn("10 Generated Questions Report", st.session_state.last_q_block, "interviews_output.pdf")