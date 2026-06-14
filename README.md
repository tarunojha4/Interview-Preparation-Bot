# 🚀 AI Interview Preparation Bot

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black.svg)](https://share.streamlit.io/tarunojha4/interview-preparation-bot/main/app.py)

An AI-powered interview preparation platform that runs on **Streamlit Cloud**. It generates mock questions, evaluates answers with **Groq + LLaMA 3.1**, and stores a searchable question bank in SQLite (auto-seeded with 50+ Data Science / ML questions).

---

## 🔗 Live App

👉 **[Run on Streamlit Cloud](https://share.streamlit.io/tarunojha4/interview-preparation-bot/main/app.py)**

---

## ✨ Features

- **Mock Interview Mode** — Sequential situational and technical questions
- **Evaluate Answer** — AI scoring with feedback out of 10
- **Hints Mode** — Progressive clues when you're stuck
- **Flashcards** — Quick revision decks
- **JD Analyzer** — Extract focus areas from job descriptions
- **Resume Questions** — Tailored questions from your profile
- **Company Prep** — Company-specific interview tracks
- **Study Roadmap** — Personalized learning paths
- **Score Dashboard** — Track performance over time
- **Timed Mode** — Practice under time pressure
- **Question Bank** — Browse 50+ pre-loaded DS/ML questions (SQLite, auto-seeded on startup)
- **Export PDF** — Download reports

---

## ☁️ Deploy on Streamlit Cloud

1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set **Repository** to `tarunojha4/interview-preparation-bot`, **Branch** `main`, **Main file** `app.py`.
4. Under **Advanced settings → Secrets**,
5.  
Get a free key at [console.groq.com](https://console.groq.com).

6. Click **Deploy**. First build installs only 4 lightweight packages (~30s vs minutes with ChromaDB).

---

## 📥 Run Locally

```bash
git clone https://github.com/tarunojha4/interview-preparation-bot.git
cd interview-preparation-bot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` (never commit this file):

```toml
GROQ_API_KEY = "your-groq-api-key"
```

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

---

## 📤 Push to GitHub

```bash
git add .
git commit -m "Optimize for Streamlit Cloud deployment"
git push origin main
```

If Streamlit Cloud is already linked to this repo, it redeploys automatically on push.

---

## 🗂️ Project Structure

```
interview-preparation-bot/
├── app.py              # Main Streamlit app (entry point)
├── requirements.txt    # Minimal dependencies for fast cloud builds
├── .streamlit/
│   └── config.toml       # Theme & server settings
└── README.md
```

---

## 🔑 Environment

| Variable | Where | Purpose |
|----------|-------|---------|
| `GROQ_API_KEY` | Streamlit secrets or `.streamlit/secrets.toml` | Groq API access |
| `DB_PATH` | Optional env var | SQLite path (default: `/tmp` on cloud) |

---

## ⚠️ Security Note

Never commit API keys or `.streamlit/secrets.toml`. If a key was ever pushed to GitHub, rotate it at [console.groq.com](https://console.groq.com).
