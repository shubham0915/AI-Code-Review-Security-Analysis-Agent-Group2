# 🎤 AI Code Review & Security Agent — Google Meet Presentation Guide

This document is your step-by-step script and guide for presenting the project on a Google Meet call. It covers the elevator pitch, architecture, technical deep-dives (like RAG and our Gatekeeper pattern), and exactly how to demonstrate the project live.

---

## ⏱️ Section 1: Introduction & The Pitch (2 Minutes)

**What to say:**
> *"Hello everyone. Today I am presenting my **AI Code Review & Security Analysis Agent**.*
so the problem faced is that 
> *Software teams lose thousands of hours to manual code reviews, and
 critical security vulnerabilities are often caught too late in the development cycle. Furthermore, standard static analysis tools just give you a warning, leaving the developer to figure out how to fix it.*
> *my solution is a **Multi-Agent, RAG-Powered Platform**. You submit Python or Java code, and five AI agents work together in parallel to automatically detect OWASP vulnerabilities, identify code smells, and instantly generate the corrected code — all without relying on expensive cloud APIs, as it is designed to run completely locally if needed."*

**Key Highlights are:**
1. **Multi-Agent:** We use 5 distinct AI agents (via LangGraph) that each have a specific job.
2. **it is RAG-Powered:** Agents don't just guess; they search a local ChromaDB vector database containing OWASP guidelines.
3. **Fail-Fast UX:** Broken code is rejected *instantly* before wasting AI resources.

--- 

## 🏗️ Section 2: Architecture & Tech Stack (3 Minutes)

**What to say:**
> *"To make this robust, we built an enterprise-grade backend architecture."*

*Share your screen and show the Architecture Diagram from the README if possible.*

**The Flow:**
1. **Frontend (Streamlit):** Where the user pastes code or uploads files.
2. **API (FastAPI):** Receives the code.
3. **Gatekeeper (Validation):**
   - We use **Google Magika ML** to instantly sniff the file and detect if it is Python or Java (blocking spoofed files like `.exe` disguised as `.py`).
   - We use **`ast.parse`** (Python) and **`javalang`** (Java) to do a 0-millisecond syntax check. If there's a missing bracket, we block it immediately.
4. **Queue (Celery + Redis):** Valid code gets an instant `session_id`, and the heavy analysis is pushed to a background Celery worker.
5. **Static Linters:** We run Bandit, Pylint, and Radon first to give the AI factual context.
6. **Agent Pipeline (LangGraph):** The AI agents execute.

**The Tech Stack (The "Things We Used"):**
- **LLMs:** Gemini 2.0 Flash (Cloud) / Ollama with Codestral & Qwen2.5 (Local)
- **Frameworks:** FastAPI, LangGraph, Streamlit, Celery
- **Database:** Redis (caching and queue), ChromaDB (Vector Store)

---

## 🧠 Section 3: Deep Dive into RAG & AI Agents (4 Minutes)

**What to say:**
> *"Let me explain how the AI actually works under the hood. We didn't just write one massive prompt. We built a pipeline."*

### 1. The RAG Pipeline (Retrieval-Augmented Generation)
* *"Instead of relying on the LLM's raw memory, we loaded 12 official OWASP security guidelines and CERT standards into our system."*
* **Chunking Strategy:** *"We didn't just split text arbitrarily. We used a `MarkdownNodeParser`. This is crucial because it respects Markdown headers and bullet points. It never cuts a document in the middle of a thought."*
* **Embedding & Storage:** *"We use embedding models (`text-embedding-004` or `nomic-embed-text`) to turn those chunks into math vectors, and store them locally in **ChromaDB**."*
* **Retrieval:** *"When the Security Agent analyzes code, it converts the code's context into a vector, searches ChromaDB for the closest OWASP guidelines, and injects them into the prompt."*

### 2. The Multi-Agent Pipeline (LangGraph)
* *"We use LangGraph to orchestrate 5 agents:"*
  1. **Code Analysis Agent:** Looks for code smells, high cyclomatic complexity, and bad design.
  2. **Security Vulnerability Agent:** Specifically hunts for OWASP Top-10 issues (SQLi, XSS, SSRF).
  3. **Remediation Agent:** Takes the findings from the first two agents and writes the actual corrected code diffs.
  4. **PR Summary Agent:** Combines everything into a final GitHub-style PR markdown review.
  5. **Conversational Assistant:** A RAG chatbot in the UI for follow-up questions.

---

## 💻 Section 4: Live Demonstration (5 Minutes)

**Before the meeting, ensure everything is running:**
```bash
docker-compose up -d                                         # Starts Redis
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000     # Terminal 1: API
celery -A app.celery_app worker -Q analysis --pool=solo -l info       # Terminal 2: Worker
streamlit run frontend/app.py                                # Terminal 3: UI
```

**Step-by-Step Demo Flow:**

### Demo 1: The Gatekeeper (Validation)
1. Open the Streamlit UI.
2. Paste some **broken Python code** (e.g., `def my_function() print("missing colon")`).
3. **Click Submit.**
4. *Show the audience:* The UI instantly rejects it with the exact line number of the syntax error. Emphasize that *zero AI tokens were wasted*.

### Demo 2: The Security Scan (SQL Injection)
1. Clear the editor and paste this vulnerable Python code:
   ```python
   import sqlite3
   def get_user_data(user_id):
       conn = sqlite3.connect('database.db')
       cursor = conn.cursor()
       # Vulnerable to SQL Injection
       query = f"SELECT * FROM users WHERE id = {user_id}"
       cursor.execute(query)
       return cursor.fetchall()
   ```
2. **Click Submit.**
3. *Show the audience:* The UI switches to "Status: Running". Explain that Celery has picked up the task in the background.
4. When it completes, walk through the **Results Dashboard**:
   - Point out the **Security Score**.
   - Show the **A03: Injection** finding found by the Security Agent.
   - Show the **Corrected Code** generated by the Remediation Agent (it should show parameterized queries like `execute("SELECT...", (user_id,))`).
   - Show the **PR Summary** at the bottom.

### Demo 3: Language Detection (File Upload)
1. Go to the "Upload File" tab.
2. Upload a simple `.java` file.
3. *Show the audience:* Explain how Magika automatically detects it as Java, validates the braces, and processes it through the same pipeline.

---

## ❓ Section 5: Anticipated Q&A

**Q: Why not just use SonarQube?**
> *"SonarQube is great for static analysis, but it only gives you alerts. Our platform uses AI to actually write the remediation code for you, and uses RAG to explain exactly *why* the code is vulnerable based on OWASP standards."*

**Q: Isn't AI code review slow?**
> *"That's why we use Celery and Redis. The API accepts the code instantly, queues it, and frees up the user. Also, by running static linters first and passing that output to the LLM, the LLM doesn't have to start from scratch, which speeds up inference."*

**Q: What if someone uploads a malicious file?**
> *"We don't trust file extensions. We use Google Magika to inspect the raw magic bytes of the file. If someone renames a `.exe` to `.py`, Magika catches the mismatch and the backend instantly drops the request before parsing it."*

---

## 📝 Presentation Checklist
- [ ] Redis is running (`docker-compose ps`)
- [ ] FastAPI server is running
- [ ] Celery worker is running
- [ ] Streamlit is running
- [ ] You have the vulnerable SQL code copied to your clipboard ready to paste
- [ ] You have a `.java` file saved on your desktop ready to upload
