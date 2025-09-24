from __future__ import annotations

import os
import sys
from pathlib import Path


CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"

CHATGPT_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"

# Qwen-specific environment variables
QWEN_AUTH_TOKEN = os.getenv("QWEN_AUTH_TOKEN")
QWEN_COOKIES = os.getenv("QWEN_COOKIES")

# ChatMock configuration
CHATMOCK_BASE_PROMPT_PATH = os.getenv("CHATMOCK_BASE_PROMPT_PATH")
CHATMOCK_RATE_LIMIT_RPS = int(os.getenv("CHATMOCK_RATE_LIMIT_RPS", "8"))
CHATMOCK_QUEUE_TIMEOUT = int(os.getenv("CHATMOCK_QUEUE_TIMEOUT", "120"))
CHATMOCK_LOG_LEVEL = os.getenv("CHATMOCK_LOG_LEVEL", "info").lower()
CHATMOCK_CORS_ORIGINS = os.getenv("CHATMOCK_CORS_ORIGINS", "*")
CHATMOCK_REQUIRE_AUTH = os.getenv("CHATMOCK_REQUIRE_AUTH", "false").lower() == "true"
CHATMOCK_ACCESS_TOKEN = os.getenv("CHATMOCK_ACCESS_TOKEN")
INJECT_BASE_PROMPT = os.getenv("INJECT_BASE_PROMPT", "true").lower() == "true"


def read_base_instructions() -> str:
    # If CHATMOCK_BASE_PROMPT_PATH is set, use it directly
    if CHATMOCK_BASE_PROMPT_PATH:
        path = Path(CHATMOCK_BASE_PROMPT_PATH)
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
            except Exception:
                pass
        raise FileNotFoundError(f"Failed to read base prompt from {CHATMOCK_BASE_PROMPT_PATH}")

    # Fallback to default candidates
    candidates = [
        Path(__file__).parent.parent / "prompt.md",
        Path(__file__).parent / "prompt.md",
        Path(getattr(sys, "_MEIPASS", "")) / "prompt.md" if getattr(sys, "_MEIPASS", None) else None,
        Path.cwd() / "prompt.md",
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if p.exists():
                content = p.read_text(encoding="utf-8")
                if isinstance(content, str) and content.strip():
                    return content
        except Exception:
            continue
    raise FileNotFoundError(
        "Failed to read prompt.md; expected adjacent to package or CWD."
    )


BASE_INSTRUCTIONS = read_base_instructions()
