from __future__ import annotations

from flask import Response, jsonify, request

from .config import CHATMOCK_CORS_ORIGINS


def build_cors_headers() -> dict:
    origin = request.headers.get("Origin", "*")
    allowed_origins = [o.strip() for o in CHATMOCK_CORS_ORIGINS.split(",") if o.strip()]
    if allowed_origins and origin not in allowed_origins and "*" not in allowed_origins:
        origin = allowed_origins[0] if allowed_origins else "*"
    req_headers = request.headers.get("Access-Control-Request-Headers")
    allow_headers = req_headers if req_headers else "Authorization, Content-Type, Accept"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": allow_headers,
        "Access-Control-Max-Age": "86400",
    }


def json_error(message: str, status: int = 400) -> Response:
    resp = jsonify({"error": {"message": message}})
    response: Response = Response(response=resp.response, status=status, mimetype="application/json")
    for k, v in build_cors_headers().items():
        response.headers.setdefault(k, v)
    return response

