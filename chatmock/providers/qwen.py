from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests
from requests import Response

from .base import Provider
from ..utils import sanitize_log_message

logger = logging.getLogger(__name__)

class QwenProvider(Provider):
    API_URL = "https://chat.qwen.ai/api/v2/chat/completions"

    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        auth_token = os.getenv("QWEN_AUTH_TOKEN")
        cookies = os.getenv("QWEN_COOKIES")
        chat_id = kwargs.get("chat_id") or os.getenv("QWEN_CHAT_ID") or "25e701db-821b-4299-b6b7-8306cbe40eb4"

        # Use QWEN_MODEL if available, otherwise use the model parameter
        qwen_model = os.getenv("QWEN_MODEL", model)

        if not auth_token:
            from flask import make_response, jsonify
            from ..http import build_cors_headers
            resp = make_response(jsonify({"error": {"message": "Missing QWEN_AUTH_TOKEN environment variable. Please set it to your Qwen authorization token."}}), 401)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return None, resp

        if not cookies:
            from flask import make_response, jsonify
            from ..http import build_cors_headers
            resp = make_response(jsonify({"error": {"message": "Missing QWEN_COOKIES environment variable. Please set it to your Qwen cookies string."}}), 401)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return None, resp

        # Generate dynamic headers
        x_request_id = str(uuid.uuid4())
        current_timezone = datetime.now(timezone.utc).strftime('%a %b %d %Y %H:%M:%S GMT%z')

        # Qwen API headers as per task
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,bg;q=0.7,zh-TW;q=0.6,zh;q=0.5",
            "Connection": "keep-alive",
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Referer": f"https://chat.qwen.ai/c/{chat_id}",
            "Host": "chat.qwen.ai",
            "Origin": "https://chat.qwen.ai",
            "DNT": "1",
            "bx-v": "2.5.31",
            "source": "web",
            "timezone": current_timezone,
            "version": "0.0.209",
            "x-accel-buffering": "no",
            "x-request-id": x_request_id,
            "authorization": f"Bearer {auth_token}",
            "Cookie": cookies,
        }

        # Qwen API payload with required fields
        payload = {
            "messages": messages,
            "stream": stream,
            "incremental_output": True,
            "chat_mode": "normal",
            "model": qwen_model,
        }

        url = f"{self.API_URL}?chat_id={chat_id}"

        def _make_request():
            try:
                resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=600)
                if resp.status_code >= 400:
                    sanitized_text = sanitize_log_message(resp.text)
                    logger.error(f"Qwen API error: {resp.status_code} - {sanitized_text}")
                    from flask import make_response, jsonify
                    from ..http import build_cors_headers
                    error_resp = make_response(jsonify({"error": {"message": resp.text}}), resp.status_code)
                    for k, v in build_cors_headers().items():
                        error_resp.headers.setdefault(k, v)
                    return None, error_resp
                return resp, None
            except requests.RequestException as e:
                sanitized_error = sanitize_log_message(str(e))
                logger.error(f"Qwen request failed: {sanitized_error}")
                from flask import make_response, jsonify
                from ..http import build_cors_headers
                resp = make_response(jsonify({"error": {"message": f"Qwen request failed: {e}"}}), 502)
                for k, v in build_cors_headers().items():
                    resp.headers.setdefault(k, v)
                return None, resp

        return self._retry_request(_make_request)

    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            upstream, error_resp = self.send_message(model, messages, stream=False, **kwargs)
            if error_resp:
                logger.error(f"Qwen error response: {error_resp.status_code} - {error_resp.text}")
                raise ValueError(f"Error: {error_resp.get_json()}")
            # Parse non-streaming response
            response_data = upstream.json()
            # Handle Qwen response structure
            choices = response_data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
            else:
                content = ""
            return {"content": content}
        except Exception as e:
            logger.error(f"Error in Qwen get_response: {str(e)}")
            raise

def parse_qwen_stream(upstream: Response, model: str, created: int) -> Generator[bytes, None, None]:
    """
    Parse Qwen's event-stream response and convert to OpenAI streaming format.
    Configurable via QWEN_STREAM_FORMAT env var (default: "content_finished").
    Expected keys: "content" for text, "finished" for completion flag.
    """
    stream_format = os.getenv("QWEN_STREAM_FORMAT", "content_finished")
    response_id = f"chatcmpl-qwen-{created}"
    for line in upstream.iter_lines(decode_unicode=False):
        if not line:
            continue
        if line.startswith(b"data: "):
            data = line[6:].decode('utf-8', errors='ignore').strip()
            if data == "[DONE]":
                # Send finish chunk
                finish_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(finish_chunk)}\n\n".encode('utf-8')
                yield b"data: [DONE]\n\n"
                break
            try:
                chunk = json.loads(data)
                # Robust key access
                content = chunk.get("content", "") if isinstance(chunk.get("content"), str) else ""
                finished = bool(chunk.get("finished", False))
                logger.debug(f"Parsed Qwen chunk: content_len={len(content)}, finished={finished}")
                if content:
                    # Send content chunk
                    delta = {"content": content}
                    openai_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(openai_chunk)}\n\n".encode('utf-8')
                if finished:
                    # Send finish chunk separately
                    finish_chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                    }
                    yield f"data: {json.dumps(finish_chunk)}\n\n".encode('utf-8')
                    yield b"data: [DONE]\n\n"
                    break
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Qwen stream data: {data[:100]}... Error: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error parsing Qwen stream: {e}")
                continue