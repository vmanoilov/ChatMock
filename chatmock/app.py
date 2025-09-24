from __future__ import annotations

import logging
from flask import Flask, jsonify

from .config import BASE_INSTRUCTIONS, CHATMOCK_LOG_LEVEL
from .http import build_cors_headers
from .routes_ollama import ollama_bp
from .routes_providers import providers_bp


def create_app(
    verbose: bool = False,
    provider: str = "chatgpt",
    model: str | None = None,
    reasoning_effort: str = "medium",
    reasoning_summary: str = "auto",
    reasoning_compat: str = "think-tags",
    debug_model: str | None = None,
    expose_reasoning_models: bool = False,
    log_level: str = "info",
    inject_base_prompt: bool = True,
) -> Flask:
    app = Flask(__name__)

    # Set up logging
    log_level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }
    logging.basicConfig(level=log_level_map.get(log_level, logging.INFO))

    app.config.update(
        VERBOSE=bool(verbose),
        PROVIDER=provider,
        MODEL=model,
        REASONING_EFFORT=reasoning_effort,
        REASONING_SUMMARY=reasoning_summary,
        REASONING_COMPAT=reasoning_compat,
        DEBUG_MODEL=debug_model,
        BASE_INSTRUCTIONS=BASE_INSTRUCTIONS,
        EXPOSE_REASONING_MODELS=bool(expose_reasoning_models),
        LOG_LEVEL=log_level,
        INJECT_BASE_PROMPT=bool(inject_base_prompt),
    )

    # Metrics counters
    metrics = {
        "requests_total": 0,
        "requests_streaming": 0,
        "requests_non_streaming": 0,
        "errors_total": 0,
        "rate_limit_hits": 0,
    }

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.get("/metrics")
    def get_metrics():
        return jsonify(metrics)

    @app.after_request
    def _cors(resp):
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    app.register_blueprint(providers_bp)
    app.register_blueprint(ollama_bp)

    return app
