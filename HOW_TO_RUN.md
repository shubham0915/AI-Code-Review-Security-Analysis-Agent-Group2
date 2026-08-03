# 🚀 AI Code Review & Security Analysis Agent — Step-by-Step Startup Guide

This document is your definitive reference for launching the full asynchronous multi-agent pipeline, wiping previous testing memory, and managing your background workers.

---

## 🏛️ Architecture & Terminal Overview

Running the complete end-to-end application requires **3 separate terminal windows** (or tabs), running simultaneously in your project folder (`/Users/arous/Desktop/AI-Code-Review-Security-Analysis-Agent-Group2`).

| Terminal | Service Name | Port / URL | What It Does |
| :--- | :--- | :--- | :--- |
| **Terminal 1** | **FastAPI Backend** | `localhost:8000` | Receives code submissions from the UI, runs immediate Gatekeeper syntax checks and Intent Guardrails, and drops valid analysis jobs into the Redis broker queue. |
| **Terminal 2** | **Celery Worker** | Background Process | Continuously listens to the custom Redis `"analysis"` queue. When a new job arrives, it executes the CPU-heavy LangGraph multi-agent review pipeline and saves the findings back to Redis. |
| **Terminal 3** | **Streamlit UI** | `localhost:8501` | Renders the web developer portal in your browser. Allows you to paste code, upload files, interact with the stateful conversational chat, and query the OWASP RAG knowledge base. |

---

## 🧹 Phase 1: Clean Up Previous Processes & Clear Results (Do This First!)

Before starting your app, it is important to clean up old zombie background workers and flush old caching memory so that previous testing runs do not interfere with new code submissions.

Open any terminal tab inside your project folder and execute this line-by-line sequence:

```bash
# 1. Ensure your local native Redis service is active and started via Homebrew
brew services start redis

# 2. Forcibly terminate any old or hanging Celery worker processes lingering in memory
pkill -9 -f celery

# 3. Wipe all old analysis session history, conversational checkpoints, and cached results from Redis
redis-cli flushall
```
*(Note: When you run `redis-cli flushall`, you will see the terminal respond with `OK`. If no old Celery processes existed, `pkill` will silently finish or display "No matching processes" — both are completely normal!)*

---

## 🏁 Phase 2: Step-by-Step Terminal Launch Sequence

Now that your machine state is completely clean, open **3 terminal tabs**, navigate to the project directory, and launch the services in order:

### 🟢 Terminal 1: Launch the FastAPI Backend Server
This turns on your main API gateway.

```bash
# Step 1: Navigate to project folder (if not already there)
cd /Users/arous/Desktop/AI-Code-Review-Security-Analysis-Agent-Group2

# Step 2: Activate the Python virtual environment
source .venv/bin/activate

# Step 3: Start the FastAPI application with live reloading on port 8000
uvicorn app.main:app --reload --port 8000
```
*When successful, you will see green text saying: `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`.*

---

### 🟣 Terminal 2: Launch the Celery Background Worker
Open a **second terminal tab**, navigate to the project, and start the processing worker.

```bash
# Step 1: Navigate to project folder
cd /Users/arous/Desktop/AI-Code-Review-Security-Analysis-Agent-Group2

# Step 2: Activate the Python virtual environment
source .venv/bin/activate

# Step 3: Start the Celery worker in solo execution mode listening to analysis queues
celery -A app.celery_app worker --loglevel=info -P solo -Q analysis,celery
```
*Why these flags?*
- `-P solo`: Runs in single-threaded loop mode to prevent macOS Apple Silicon multiprocessing concurrency forks from clobbering network AI libraries.
- `-Q analysis,celery`: Explicitly tells the worker to actively monitor both our custom `"analysis"` routing queue and the default `"celery"` queue simultaneously!
*When successful, you will see an ASCII logo and text saying: `celery@<your-mac> ready`.*

---

### 🟠 Terminal 3: Launch the Streamlit Interactive UI
Open a **third terminal tab**, navigate to the project, and turn on the frontend interface.

```bash
# Step 1: Navigate to project folder
cd /Users/arous/Desktop/AI-Code-Review-Security-Analysis-Agent-Group2

# Step 2: Activate the Python virtual environment
source .venv/bin/activate

# Step 3: Start the Streamlit server on port 8501
streamlit run frontend/app.py
```
*When successful, your system's default web browser will automatically spring open and direct you to **`http://localhost:8501`**!*

---

## 🧪 Phase 3: Testing & Verifying in the UI

Once your browser opens to `http://localhost:8501`, you are ready to test!
1. Open the [UI_TEST_CASES.md](./UI_TEST_CASES.md) file located directly in your project root.
2. Copy any of the test snippets (such as **Test Case 1: Python SQL & Command Injection**).
3. Paste it directly into the Streamlit code editor box, select the matching language, and click **Analyze Code**.
4. You can monitor live log events occurring across **Terminal 1** (API routing) and **Terminal 2** (AI analysis worker progress) while waiting for your review report modal to appear!

---

## 💡 Pro-Tips & Shortcuts

### ⚡ Standalone "Local Mode" (No Backend Needed)
If you ever want to perform a quick UI styling check or test syntax gatekeeping without launching multiple background processes, simply start **Terminal 3 only** (`streamlit run frontend/app.py`). The dashboard will detect that FastAPI isn't running and fall back to local browser AST syntax checking!

### 🛑 How to Shut Everything Down Cleanly
When you are finished testing and wish to stop all running services:
1. In each of your 3 terminals, press **`CTRL + C`** on your keyboard.
2. Run your terminal cleanup sequence one last time to ensure no hidden processes stay active in the background:
   ```bash
   pkill -9 -f celery && redis-cli flushall && brew services stop redis
   ```
