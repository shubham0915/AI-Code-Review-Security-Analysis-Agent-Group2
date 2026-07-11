# Architecture Evolution: Language Detection & Syntax Validation

This document tracks how our Language Detection and Syntax Validation engines evolved during Milestone 1, mapping out the initial approaches, our current state-of-the-art implementations, and potential future improvements.

## 🏗️ Evolution Summary Table

| Feature | Phase 1: The Initial Approach | Phase 2: The Current State (Latest) | Phase 3: What Can Be Improved? |
| :--- | :--- | :--- | :--- |
| **Language Detection** | **Regex Keyword Matching:** Scanned code for hardcoded keywords (`def`, `import`). *Flaw:* `import` matched both Java and Python, causing misclassification. | **Google Magika (Machine Learning):** Uses a tiny ONNX neural network to identify file contents instantly based on statistical structures. Supported by strict fallback heuristics. | **Fine-Tuned LLM Classifier:** Passing snippets to a specialized small-parameter model to understand mixed-language contexts or custom frameworks. |
| **Python Syntax Validation** | **`ast.parse()`:** Built-in Python standard library used to parse the code into an Abstract Syntax Tree. | **`ast.parse()`:** (Unchanged). It remains the fastest, most precise, and natively supported way to check Python syntax in a Python backend. | **Linting integration:** Adding `ruff` or `flake8` to detect deeper logical errors (e.g. unused imports, bad scoping) rather than just syntax formatting. |
| **Java Syntax Validation** | **Regex Heuristics & `javac` Subprocess:** Initially just counted `{}` braces. Then upgraded to writing temporary files to disk and booting up the heavy Java Compiler (`javac`). *Flaw:* Very slow and requires the server to have a Java JDK installed. | **`javalang` (Pure Python AST):** We replaced the heavy `javac` subprocess with a lightweight, pure Python library. It instantly parses Java code in-memory just like Python's `ast.parse()`, with 0 millisecond delay. | **Tree-sitter:** Upgrading to `tree-sitter-java`, which is the industry standard (used by VS Code / GitHub) for ultra-fast, robust, error-tolerant syntax parsing. |
| **File Upload Security** | **Blind Extension Trust:** Relied purely on the uploaded file's extension (e.g. `.py` was assumed to be Python). *Flaw:* Vulnerable to spoofing (e.g., uploading a `virus.exe` renamed to `main.py`). | **Magic Byte Content Sniffing:** We pass the raw file bytes through Magika AI. If the file claims to be Python (`.py`) but the AI detects C++ or Executable binaries, we instantly block it with an `Extension Mismatch` error. | **Deep Content Scanning:** Pre-scanning the file for known malware signatures or shell-code patterns before even running the language detection layer. |
| **UI Gatekeeper UX** | **Reactive Validation:** The "Submit" button was always clickable, but would throw an error *after* you clicked it if the code was invalid. | **Proactive Fail-Fast UX:** The "Submit" buttons are now dynamically bound to the live syntax state. If there is a syntax error or mismatch, the buttons become **completely disabled and greyed out**. | **Inline Editor Diagnostics:** Highlighting the exact character inside the Monaco code editor with a red squiggly line, rather than just showing the error below the editor. |

---

## 🔍 Detailed Breakdown

### 1. Language Detection: How do we know if it's Java or Python?
We must identify the language *before* validating to ensure we use the correct parser.

* **What we used first:** A naive string matching system. If the code contained `public class`, it scored 1 for Java. If it contained `def `, it scored 1 for Python. Python won all ties.
* **What we use NOW:** We integrated **Magika** (by Google). Magika uses deep learning to identify the language in milliseconds. If Magika determines a snippet is JavaScript, HTML, or C++, our system strictly rejects it as an "Unsupported Language" rather than guessing.
* **Further Improvement:** If we wanted to support dozens of languages, we could integrate GitHub's `Linguist` library or offload detection to an extremely fast, quantized LLM.

### 2. Syntax Validation: Catching the errors
Validation acts as our **"Gatekeeper"**. If code fails validation, the pipeline stops instantly. It is never sent to the expensive AI Agents for deep review.

* **What we used first for Java:** We saved the code to a hidden file and triggered the system terminal to run `javac Main.java`. While this accurately caught errors, spinning up a Java Virtual Machine on every keystroke was extremely heavy on CPU resources.
* **What we use NOW for Java:** We use **`javalang`**, a pure Python library. It parses Java code directly in the server's memory without needing Java installed on the host machine. It returns the exact Line and Column number of the syntax error instantly.
* **Further Improvement:** `javalang` is excellent, but for enterprise-grade parsing that can gracefully handle heavily broken code, **`tree-sitter`** is the gold standard used by modern IDEs.

### 3. File Upload Security (Magic Byte Sniffing)
Malicious users often try to bypass security filters by simply renaming a file (e.g., renaming a C++ payload or executable to `safe_script.py`).

* **Our Current State-of-the-Art Defense:** We implemented **"Content Sniffing"**. Even if a user uploads a file with a `.py` extension, we do not blindly trust it. We feed the raw bytes into the Magika AI model. If Magika detects that the file is actually `cpp` or `binary`, we instantly trigger a massive `Extension Mismatch` error and block the submission.

### 4. Proactive UI UX (The Gatekeeper)
A Gatekeeper should not let you try to walk through a locked door; the door should simply not open.

* **Our Current Implementation:** The "Submit for Analysis" buttons in the Streamlit UI are strictly bound to the local live-validation state. If the code contains a syntax error or triggers an extension mismatch, the submit buttons are completely greyed out and disabled. This perfectly synchronizes the user experience with our backend architectural rules!
