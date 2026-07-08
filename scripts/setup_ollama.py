#!/usr/bin/env python3
"""
scripts/setup_ollama.py — Pull all required Ollama models.

Run this once before starting the application.
Usage: python scripts/setup_ollama.py
"""
import subprocess
import sys


MODELS = [
    ("nomic-embed-text", "Embedding model (768-dim, MPS accelerated)"),
    ("codestral", "Primary LLM for security + remediation agents"),
    ("qwen2.5-coder:7b", "Fast LLM for code analysis + PR summary agents"),
]


def check_ollama() -> bool:
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=10)
        print(f"✅ Ollama found: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ Ollama not found. Install from: https://ollama.com/download")
        return False
    except Exception as e:
        print(f"❌ Ollama check failed: {e}")
        return False


def pull_model(model_name: str, description: str) -> bool:
    print(f"\n📥 Pulling: {model_name}")
    print(f"   {description}")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            check=True,
            timeout=600,   # 10 minutes
        )
        print(f"✅ {model_name} ready")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to pull {model_name}: {e}")
        return False
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout pulling {model_name}. Try running: ollama pull {model_name}")
        return False


def list_local_models() -> list[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().split("\n")[1:]   # Skip header
        return [line.split()[0] for line in lines if line.strip()]
    except Exception:
        return []


def main():
    print("=" * 60)
    print("AI Code Review Agent — Ollama Model Setup")
    print("=" * 60)

    if not check_ollama():
        sys.exit(1)

    local_models = list_local_models()
    print(f"\n📋 Already installed: {local_models or 'none'}")

    success_count = 0
    for model_name, description in MODELS:
        # Check if already installed (partial name match)
        already_installed = any(model_name in m for m in local_models)
        if already_installed:
            print(f"\n✅ {model_name} — already installed, skipping.")
            success_count += 1
            continue

        if pull_model(model_name, description):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"Setup complete: {success_count}/{len(MODELS)} models ready")
    if success_count == len(MODELS):
        print("✅ All models ready. You can now start the backend:")
        print("   uvicorn app.main:app --reload")
    else:
        print("⚠️  Some models failed. Run 'ollama pull <model>' manually.")
    print("=" * 60)


if __name__ == "__main__":
    main()
