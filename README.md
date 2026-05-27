# 🚀 AI Interview Preparation Bot

An advanced, end-to-end local AI-powered platform designed to mentor and prepare candidates for core technical interviews. The platform conducts dynamic mock interviews, reviews core system layouts, grades answer quality using a local Large Language Model (LLM), and maintains records via a local Vector Database for continuous analysis.

Built with a **100% Local & Private Architecture**—ensuring absolute data privacy and zero dependency on commercial cloud APIs.

---

## 🛠️ Tech Stack

- **Frontend Core:** `Streamlit` (Dashboard interface with dynamic component views)
- **Local Intelligence:** `Ollama` + `LLaMA 3` (On-device reasoning, custom evaluation & scoring)
- **Vector Storage:** `ChromaDB` + `HuggingFace Embeddings (all-MiniLM-L6-v2)` (Semantic query routing)
- **Environment Stack:** `Python 3.11+` / Virtual Environment (`venv`)

---

## ✨ Advanced Features & Modules

Aapko is bot mein complete preparation ke liye custom features milte hain:

1. **🤖 Mock Interview Mode:** Generates situational and algorithmic questions sequentially based on tech stack, experience level (Fresher/Junior/Senior), and difficulty.
2. **🧠 Evaluate Answer:** Analyzes user responses locally to give transparent breakdown critiques and assignment scores out of 10.
3. **💡 Hints Mode:** Provides dynamic contextual clues if the candidate gets stuck mid-thought during a solution structure.
4. **⚡ Flashcards:** Interactive revision decks for quick conceptual sweeps over key system properties and parameters.
5. **📄 JD Analyzer:** Parses job descriptions to automatically extract expected focus areas, stacks, and custom question expectations.
6. **📝 Resume Questions:** Tailors highly specific architectural questions by screening user profile history and listed tech tools.
7. **🏢 Company Prep:** Curates standard past interview tracks from top tech entities according to target domain data.
8. **🗺️ Study Roadmap:** Computes tailored learning path trajectories with milestone schedules depending on current skill gaps.
9. **📈 Score Dashboard:** Visualizes history matrices over past performances to identify structural progression trends.
10. **⏱️ Timed Mode:** Adds real-time clock pressures to evaluation pipelines to replicate practical pressurized coding tracks.
11. **📚 Question Bank:** Offers a centralized local knowledge index to query or revisit past mock transcripts.
12. **🗂️ Export PDF:** Generates portable formatted analytics reports of historical interview feedbacks for offline usage.

---

## 🚀 How to Run the Project (Installation Guide)

Follow these clear steps to launch the complete application on your workstation:

### 1. Clone the Codebase
```bash
git clone [https://github.com/tarunojha4/interview-preparation-bot.git](https://github.com/tarunojha4/interview-preparation-bot.git)
cd interview-preparation-bot