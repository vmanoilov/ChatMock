from __future__ import annotations

import json
import logging
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional, Tuple

import requests
from requests import Response

from .config import CHATGPT_RESPONSES_URL
from .providers.qwen import QwenProvider
from .session import ensure_session_id
from .upstream import normalize_model_name
from .utils import get_effective_chatgpt_auth, convert_chat_messages_to_responses_input

logger = logging.getLogger(__name__)

class Provider(ABC):
    @abstractmethod
    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        """Send message to provider, return upstream response and error response."""
        pass

    @abstractmethod
    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """Get non-streaming response from provider."""
        pass

    def _retry_request(self, make_request, max_retries: int = 6) -> Tuple[Optional[Response], Optional[Response]]:
        delay = 0.5
        for attempt in range(max_retries):
            upstream, error_resp = make_request()
            if error_resp is not None:
                return upstream, error_resp
            if upstream is None or upstream.status_code != 429:
                if upstream is None:
                    logger.error("Upstream request failed with no response")
                return upstream, None
            # 429 retry
            ra = upstream.headers.get("retry-after")
            if ra:
                try:
                    sleep_for = float(ra)
                except ValueError:
                    sleep_for = 2.0
            else:
                sleep_for = min(15.0, delay)
                delay *= 2
            sleep_for += random.uniform(0.1, 0.4)
            time.sleep(sleep_for)
        return upstream, None

class ChatGPTProvider(Provider):
    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, instructions: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None, tool_choice: Any = "auto", parallel_tool_calls: bool = False, reasoning_param: Optional[Dict[str, Any]] = None, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        access_token, account_id = get_effective_chatgpt_auth()
        if not access_token or not account_id:
            from flask import make_response, jsonify
            from .http import build_cors_headers
            resp = make_response(jsonify({"error": {"message": "Missing ChatGPT credentials. Run 'python3 chatmock.py login' first."}}), 401)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return None, resp

        model = normalize_model_name(model)
        input_items = convert_chat_messages_to_responses_input(messages)
        client_session_id = kwargs.get('session_id')
        session_id = ensure_session_id(instructions, input_items, client_session_id)

        payload = {
            "model": model,
            "instructions": instructions,
            "input": input_items,
            "tools": tools or [],
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "store": False,
            "stream": stream,
            "prompt_cache_key": session_id,
        }
        if reasoning_param:
            payload["reasoning"] = reasoning_param
            payload["include"] = ["reasoning.encrypted_content"]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "chatgpt-account-id": account_id,
            "OpenAI-Beta": "responses=experimental",
            "session_id": session_id,
        }

        def _make_request():
            try:
                return requests.post(CHATGPT_RESPONSES_URL, headers=headers, json=payload, stream=True, timeout=600), None
            except requests.RequestException as e:
                from flask import make_response, jsonify
                from .http import build_cors_headers
                resp = make_response(jsonify({"error": {"message": f"Upstream ChatGPT request failed: {e}"}}), 502)
                for k, v in build_cors_headers().items():
                    resp.headers.setdefault(k, v)
                return None, resp

        return self._retry_request(_make_request)

    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            upstream, error_resp = self.send_message(model, messages, stream=False, **kwargs)
            if error_resp:
                logger.error(f"ChatGPT error response: {error_resp.status_code} - {error_resp.text}")
                raise ValueError(f"Error: {error_resp.get_json()}")
            # Implement non-streaming parsing similar to routes_openai.py
            full_text = ""
            for line in upstream.iter_lines():
                if line.startswith(b"data: "):
                    data = line[6:].decode('utf-8').strip()
                    if data == "[DONE]":
                        break
                    try:
                        evt = json.loads(data)
                        if evt.get("type") == "response.output_text.delta":
                            full_text += evt.get("delta", "")
                    except json.JSONDecodeError:
                        continue
            return {"content": full_text}
        except Exception as e:
            logger.error(f"Error in ChatGPT get_response: {str(e)}")
            raise

class GrokProvider(Provider):
    API_URL = "https://api.x.ai/v1/chat/completions"

    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            from flask import make_response, jsonify
            from .http import build_cors_headers
            resp = make_response(jsonify({"error": {"message": "Missing XAI_API_KEY environment variable."}}), 401)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return None, resp

        # Map to "grok-beta" for Code Fast 1
        model = "grok-beta"

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": kwargs.get("temperature", 0.7),
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _make_request():
            try:
                resp = requests.post(self.API_URL, headers=headers, json=payload, stream=True, timeout=600)
                if resp.status_code >= 400:
                    logger.error(f"Grok API error: {resp.status_code} - {resp.text}")
                    from flask import make_response, jsonify
                    from .http import build_cors_headers
                    error_resp = make_response(jsonify({"error": {"message": resp.text}}), resp.status_code)
                    for k, v in build_cors_headers().items():
                        error_resp.headers.setdefault(k, v)
                    return None, error_resp
                return resp, None
            except requests.RequestException as e:
                logger.error(f"Grok request failed: {e}")
                from flask import make_response, jsonify
                from .http import build_cors_headers
                resp = make_response(jsonify({"error": {"message": f"Grok request failed: {e}"}}), 502)
                for k, v in build_cors_headers().items():
                    resp.headers.setdefault(k, v)
                return None, resp

        return self._retry_request(_make_request)

    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            upstream, error_resp = self.send_message(model, messages, stream=False, **kwargs)
            if error_resp:
                logger.error(f"Grok error response: {error_resp.status_code} - {error_resp.text}")
                raise ValueError(f"Error: {error_resp.get_json()}")
            response_data = upstream.json()
            content = response_data["choices"][0]["message"]["content"]
            return {"content": content}
        except Exception as e:
            logger.error(f"Error in Grok get_response: {str(e)}")
            raise

class OpenRouterProvider(Provider):
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    MAX_TOKENS = 1000000  # 1M token limit

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total_chars = sum(len(str(msg)) for msg in messages)
        return total_chars // 4  # Rough estimate: 4 chars per token

    def _truncate_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        est_tokens = self._estimate_tokens(messages)
        if est_tokens <= self.MAX_TOKENS:
            return messages
        # Simple truncation: keep last messages until under limit
        from tqdm import tqdm
        truncated = []
        for msg in tqdm(reversed(messages), total=len(messages), desc="Truncating context", unit="msg"):
            truncated.insert(0, msg)
            if self._estimate_tokens(truncated) > self.MAX_TOKENS:
                truncated.pop(0)
        return truncated

    def send_message(self, model: str, messages: List[Dict[str, Any]], stream: bool = True, **kwargs) -> Tuple[Optional[Response], Optional[Response]]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            from flask import make_response, jsonify
            from .http import build_cors_headers
            resp = make_response(jsonify({"error": {"message": "Missing OPENROUTER_API_KEY environment variable."}}), 401)
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return None, resp

        # Map to sonoma/sky or sonoma/dusk
        if "sonoma-dusk" in model.lower():
            model = "sonoma/dusk"
        elif "sonoma-sky" in model.lower():
            model = "sonoma/sky"
        else:
            model = "sonoma/sky"  # Default

        messages = self._truncate_messages(messages)

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "temperature": kwargs.get("temperature", 0.7),
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": kwargs.get("provider", "ChatMock"),
            "X-Title": kwargs.get("provider", "ChatMock"),
        }

        def _make_request():
            try:
                resp = requests.post(self.API_URL, headers=headers, json=payload, stream=True, timeout=600)
                if resp.status_code >= 400:
                    logger.error(f"OpenRouter API error: {resp.status_code} - {resp.text}")
                    from flask import make_response, jsonify
                    from .http import build_cors_headers
                    error_resp = make_response(jsonify({"error": {"message": resp.text}}), resp.status_code)
                    for k, v in build_cors_headers().items():
                        error_resp.headers.setdefault(k, v)
                    return None, error_resp
                return resp, None
            except requests.RequestException as e:
                logger.error(f"OpenRouter request failed: {e}")
                from flask import make_response, jsonify
                from .http import build_cors_headers
                resp = make_response(jsonify({"error": {"message": f"OpenRouter request failed: {e}"}}), 502)
                for k, v in build_cors_headers().items():
                    resp.headers.setdefault(k, v)
                return None, resp

        return self._retry_request(_make_request)

    def get_response(self, model: str, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        try:
            upstream, error_resp = self.send_message(model, messages, stream=False, **kwargs)
            if error_resp:
                logger.error(f"OpenRouter error response: {error_resp.status_code} - {error_resp.text}")
                raise ValueError(f"Error: {error_resp.get_json()}")
            response_data = upstream.json()
            content = response_data["choices"][0]["message"]["content"]
            return {"content": content}
        except Exception as e:
            logger.error(f"Error in OpenRouter get_response: {str(e)}")
            raise

PROVIDERS = {
    "chatgpt": ChatGPTProvider(),
    "grok": GrokProvider(),
    "openrouter": OpenRouterProvider(),
    "qwen": QwenProvider(),
}