from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

import requests
from requests import Response

from ..utils import sanitize_log_message

logger = logging.getLogger(__name__)


class ChatMockError(Exception):
    def __init__(self, kind: str, status: int, message: str, retry_after: Optional[int] = None):
        self.kind = kind
        self.status = status
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


class QwenClient:
    def __init__(self, base_url: str, auth_token: Optional[str] = None, cookies: Optional[str] = None, timeout: int = 600):
        self.base_url = base_url
        self.auth_token = auth_token
        self.cookies = cookies
        self.timeout = timeout

    def chat(self, messages: List[Dict[str, Any]], stream: bool = False, **opts) -> Dict[str, Any] | Generator[str, None, None]:
        """
        Send chat request to Qwen API.

        Args:
            messages: List of message dicts
            stream: Whether to stream response
            **opts: Additional options like temperature, top_p, max_tokens, chat_id, model

        Returns:
            Non-stream: {"text": "...", "usage": {...}}
            Stream: Generator yielding text chunks, then final "stop" signal
        """
        chat_id = opts.get("chat_id") or os.getenv("QWEN_CHAT_ID") or "25e701db-821b-4299-b6b7-8306cbe40eb4"
        model = opts.get("model") or os.getenv("QWEN_MODEL", "qwen3-max-preview")
        temperature = opts.get("temperature", 0.7)
        top_p = opts.get("top_p", 1.0)
        max_tokens = opts.get("max_tokens", 1024)

        # Normalize messages to Qwen format
        normalized_messages = self._normalize_messages(messages)

        # Generate dynamic headers
        x_request_id = str(uuid.uuid4())
        current_timezone = datetime.now(timezone.utc).strftime('%a %b %d %Y %H:%M:%S GMT%z')

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
        }

        if self.auth_token:
            headers["authorization"] = f"Bearer {self.auth_token}"
        if self.cookies:
            headers["Cookie"] = self.cookies

        payload = {
            "messages": normalized_messages,
            "stream": stream,
            "incremental_output": True,
            "chat_mode": "normal",
            "model": model,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        url = f"{self.base_url}?chat_id={chat_id}"

        try:
            resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=self.timeout)
            if resp.status_code >= 400:
                sanitized_text = sanitize_log_message(resp.text)
                logger.error(f"Qwen API error: {resp.status_code} - {sanitized_text}")
                retry_after = None
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("retry-after", 2))
                raise ChatMockError("upstream", resp.status_code, resp.text, retry_after)

            if stream:
                return self._parse_stream(resp, model)
            else:
                return self._parse_non_stream(resp)

        except requests.RequestException as e:
            sanitized_error = sanitize_log_message(str(e))
            logger.error(f"Qwen request failed: {sanitized_error}")
            raise ChatMockError("upstream", 502, f"Qwen request failed: {e}")

    def _normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize messages to Qwen expected format."""
        # Qwen expects standard OpenAI format, so minimal changes needed
        return messages

    def _parse_non_stream(self, resp: Response) -> Dict[str, Any]:
        """Parse non-streaming response."""
        response_data = resp.json()
        choices = response_data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
        else:
            content = ""
        usage = response_data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
        return {"text": content, "usage": usage}

    def _parse_stream(self, resp: Response, model: str) -> Generator[str, None, None]:
        """Parse streaming response, yielding text chunks."""
        for line in resp.iter_lines(decode_unicode=False):
            if not line:
                continue
            if line.startswith(b"data: "):
                data = line[6:].decode('utf-8', errors='ignore').strip()
                if data == "[DONE]":
                    yield "stop"  # Final signal
                    break
                try:
                    chunk = json.loads(data)
                    content = chunk.get("content", "") if isinstance(chunk.get("content"), str) else ""
                    finished = bool(chunk.get("finished", False))
                    logger.debug(f"Parsed Qwen chunk: content_len={len(content)}, finished={finished}")
                    if content:
                        yield content
                    if finished:
                        yield "stop"
                        break
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Qwen stream data: {data[:100]}... Error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error parsing Qwen stream: {e}")
                    continue