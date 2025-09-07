from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

from flask import Blueprint, Response, current_app, jsonify, make_response, request
from requests import Response as RequestsResponse

from .config import BASE_INSTRUCTIONS
from .http import build_cors_headers
from .providers import PROVIDERS
from .rate_limit import gate, GateBusy, queue_timeout_seconds
from .reasoning import apply_reasoning_to_message, build_reasoning_param, extract_reasoning_from_model_name
from .upstream import normalize_model_name
from .utils import (
    convert_chat_messages_to_responses_input,
    convert_tools_chat_to_responses,
    sse_translate_chat,
    sse_translate_text,
)

logger = logging.getLogger(__name__)

providers_bp = Blueprint("providers", __name__)

def get_provider(provider_name: str = None):
    provider_name = provider_name or current_app.config.get('PROVIDER', 'chatgpt')
    provider = PROVIDERS.get(provider_name.lower())
    if not provider:
        return None, f"Invalid provider: {provider_name}. Available: {list(PROVIDERS.keys())}"
    return provider, None

def handle_error(error_msg, status=400):
    resp = make_response(jsonify({"error": {"message": error_msg}}), status)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp

@providers_bp.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    verbose = bool(current_app.config.get("VERBOSE"))
    reasoning_effort = current_app.config.get("REASONING_EFFORT", "medium")
    reasoning_summary = current_app.config.get("REASONING_SUMMARY", "auto")
    reasoning_compat = current_app.config.get("REASONING_COMPAT", "think-tags")
    debug_model = current_app.config.get("DEBUG_MODEL")
    default_model = current_app.config.get('MODEL')

    provider_name = request.args.get('provider') or current_app.config.get('PROVIDER', 'chatgpt')
    provider, err = get_provider(provider_name)
    if err:
        return handle_error(err, 400)

    if verbose:
        try:
            body_preview = (request.get_data(cache=True, as_text=True) or "")[:2000]
            print(f"IN POST /v1/chat/completions (provider: {provider_name})\n{body_preview}")
        except Exception:
            pass

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return handle_error("Invalid JSON body")

    requested_model = payload.get("model") or default_model
    model = requested_model or "gpt-5"
    messages = payload.get("messages")
    if messages is None and isinstance(payload.get("prompt"), str):
        messages = [{"role": "user", "content": payload.get("prompt") or ""}]
    if messages is None:
        messages = []
    if not isinstance(messages, list):
        return handle_error("Request must include messages: []")

    is_stream = bool(payload.get("stream"))
    stream_options = payload.get("stream_options") or {}
    include_usage = bool(stream_options.get("include_usage", False))

    tools_responses = convert_tools_chat_to_responses(payload.get("tools"))
    tool_choice = payload.get("tool_choice", "auto")
    parallel_tool_calls = bool(payload.get("parallel_tool_calls", False))

    if provider_name == "chatgpt":
        # ChatGPT specific
        if isinstance(messages, list):
            sys_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)
            if sys_idx is not None:
                sys_msg = messages.pop(sys_idx)
                content = sys_msg.get("content") or ""
                messages.insert(0, {"role": "user", "content": content})

        input_items = convert_chat_messages_to_responses_input(messages)
        model_reasoning = extract_reasoning_from_model_name(requested_model)
        reasoning_overrides = payload.get("reasoning") or model_reasoning
        reasoning_param = build_reasoning_param(reasoning_effort, reasoning_summary, reasoning_overrides)

        try:
            permit = gate.acquire(wait_timeout=queue_timeout_seconds)
        except GateBusy as gb:
            resp = handle_error("Server busy, please retry", 429)
            resp.headers["Retry-After"] = str(gb.retry_after_seconds)
            return resp

        upstream, error_resp = provider.send_message(
            model=normalize_model_name(model, debug_model),
            messages=messages,
            stream=is_stream,
            instructions=BASE_INSTRUCTIONS,
            tools=tools_responses,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            reasoning_param=reasoning_param,
        )
        if error_resp:
            permit.release()
            return error_resp

        created = int(time.time())
        if upstream.status_code >= 400:
            try:
                err_body = json.loads(upstream.content.decode("utf-8", errors="ignore")) if upstream.content else {"raw": upstream.text}
            except Exception:
                err_body = {"raw": upstream.text}
            logger.error(f"ChatGPT upstream error: {upstream.status_code} - {err_body}")
            permit.release()
            headers = {}
            if "retry-after" in upstream.headers:
                headers["Retry-After"] = upstream.headers["retry-after"]
            return handle_error(err_body.get("error", {}).get("message", "Upstream error"), upstream.status_code), headers

        if is_stream:
            def wrap_stream(gen):
                try:
                    for chunk in gen:
                        yield chunk
                finally:
                    permit.release()

            resp = Response(
                wrap_stream(sse_translate_chat(
                    upstream,
                    requested_model or model,
                    created,
                    verbose=verbose,
                    vlog=print if verbose else None,
                    reasoning_compat=reasoning_compat,
                    include_usage=include_usage,
                )),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        # Non-streaming ChatGPT
        full_text = ""
        tool_calls = []
        usage = None
        response_id = "chatcmpl"
        try:
            for line in upstream.iter_lines(decode_unicode=False):
                if not line:
                    continue
                data = line.decode("utf-8", errors="ignore").strip()
                if data.startswith("data: "):
                    data = data[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        evt = json.loads(data)
                        if evt.get("type") == "response.output_text.delta":
                            full_text += evt.get("delta", "")
                        # Add other event handling as in original
                    except json.JSONDecodeError:
                        continue
        finally:
            permit.release()

        message = {"role": "assistant", "content": full_text}
        if tool_calls:
            message["tool_calls"] = tool_calls
        completion = {
            "id": response_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": usage or {},
        }
        resp = make_response(jsonify(completion))
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    else:
        # Generic providers
        try:
            permit = gate.acquire(wait_timeout=queue_timeout_seconds)
        except GateBusy as gb:
            resp = handle_error("Server busy, please retry", 429)
            resp.headers["Retry-After"] = str(gb.retry_after_seconds)
            return resp

        upstream, error_resp = provider.send_message(
            model=model,
            messages=messages,
            stream=is_stream,
            temperature=payload.get("temperature", 0.7),
        )
        if error_resp:
            permit.release()
            return error_resp

        created = int(time.time())
        if upstream.status_code >= 400:
            try:
                err_body = upstream.json()
            except Exception:
                err_body = {"raw": upstream.text}
            logger.error(f"{provider_name} upstream error: {upstream.status_code} - {err_body}")
            permit.release()
            return handle_error(err_body.get("error", {}).get("message", "Upstream error"), upstream.status_code)

        if is_stream:
            def generic_sse_stream(upstream_resp):
                try:
                    for line in upstream_resp.iter_lines(decode_unicode=False):
                        if not line:
                            continue
                        if line == b"data: [DONE]":
                            yield b"data: [DONE]\n\n"
                            break
                        if line.startswith(b"data: "):
                            data = line[6:].decode('utf-8', errors='ignore').strip()
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                json_str = json.dumps({'choices': [{'delta': {'content': delta}}]})
                                yield f"data: {json_str}\n\n".encode('utf-8')
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    pass
                finally:
                    permit.release()

            resp = Response(
                generic_sse_stream(upstream),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp

        # Non-streaming generic
        try:
            response_data = upstream.json()
            choices = response_data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")
            else:
                content = ""
            usage = response_data.get("usage", {})
            completion = {
                "id": response_data.get("id", "chatcmpl"),
                "object": "chat.completion",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": usage,
            }
            resp = make_response(jsonify(completion))
            for k, v in build_cors_headers().items():
                resp.headers.setdefault(k, v)
            return resp
        finally:
            permit.release()

@providers_bp.route("/v1/completions", methods=["POST"])
def completions():
    # Similar structure to chat_completions, but for text completions
    verbose = bool(current_app.config.get("VERBOSE"))
    debug_model = current_app.config.get("DEBUG_MODEL")
    default_model = current_app.config.get('MODEL')
    provider_name = request.args.get('provider') or current_app.config.get('PROVIDER', 'chatgpt')
    provider, err = get_provider(provider_name)
    if err:
        return handle_error(err, 400)

    raw = request.get_data(cache=True, as_text=True) or ""
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return handle_error("Invalid JSON body")

    requested_model = payload.get("model") or default_model
    model = requested_model or "gpt-5"
    prompt = payload.get("prompt", "")
    if isinstance(prompt, list):
        prompt = "".join(str(p) for p in prompt)
    stream_req = bool(payload.get("stream", False))
    stream_options = payload.get("stream_options") or {}
    include_usage = bool(stream_options.get("include_usage", False))

    messages = [{"role": "user", "content": prompt}]

    try:
        permit = gate.acquire(wait_timeout=queue_timeout_seconds)
    except GateBusy as gb:
        resp = handle_error("Server busy, please retry", 429)
        resp.headers["Retry-After"] = str(gb.retry_after_seconds)
        return resp

    if provider_name == "chatgpt":
        input_items = convert_chat_messages_to_responses_input(messages)
        reasoning_param = build_reasoning_param(current_app.config.get("REASONING_EFFORT", "medium"), current_app.config.get("REASONING_SUMMARY", "auto"))

        upstream, error_resp = provider.send_message(
            model=normalize_model_name(model, debug_model),
            messages=messages,
            stream=stream_req,
            instructions=BASE_INSTRUCTIONS,
            reasoning_param=reasoning_param,
        )
        if error_resp:
            permit.release()
            return error_resp
    else:
        upstream, error_resp = provider.send_message(
            model=model,
            messages=messages,
            stream=stream_req,
            temperature=payload.get("temperature", 0.7),
        )
        if error_resp:
            permit.release()
            return error_resp

    created = int(time.time())
    if upstream.status_code >= 400:
        try:
            err_body = upstream.json()
        except Exception:
            err_body = {"raw": upstream.text}
        logger.error(f"{provider_name} completions error: {upstream.status_code} - {err_body}")
        permit.release()
        return handle_error("Upstream error", upstream.status_code)

    if stream_req:
        if provider_name == "chatgpt":
            def wrap():
                try:
                    for chunk in sse_translate_text(upstream, model, created, verbose=verbose, include_usage=include_usage):
                        yield chunk
                finally:
                    permit.release()
            resp = Response(wrap(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
        else:
            def generic_text_stream(upstream_resp):
                try:
                    for line in upstream_resp.iter_lines(decode_unicode=False):
                        if line.startswith(b"data: "):
                            data = line[6:].decode('utf-8').strip()
                            if data == "[DONE]":
                                yield b"data: [DONE]\n\n"
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                json_str = json.dumps({'choices': [{'text': delta}]})
                                yield f"data: {json_str}\n\n".encode('utf-8')
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    pass
                finally:
                    permit.release()
            resp = Response(generic_text_stream(upstream), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
        for k, v in build_cors_headers().items():
            resp.headers.setdefault(k, v)
        return resp

    # Non-streaming
    full_text = ""
    if provider_name == "chatgpt":
        for line in upstream.iter_lines(decode_unicode=False):
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
    else:
        response_data = upstream.json()
        choices = response_data.get("choices", [])
        full_text = choices[0].get("text", "") if choices else ""

    permit.release()
    completion = {
        "id": "cmpl-1",
        "object": "text_completion",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "text": full_text, "finish_reason": "stop"}],
        "usage": upstream.json().get("usage", {}) if not provider_name == "chatgpt" else {},
    }
    resp = make_response(jsonify(completion))
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp

@providers_bp.route("/v1/models", methods=["GET"])
def list_models():
    expose_variants = bool(current_app.config.get("EXPOSE_REASONING_MODELS"))
    all_models = []

    for provider_name in PROVIDERS:
        if provider_name == "chatgpt":
            if expose_variants:
                models = ["gpt-5", "gpt-5-high", "gpt-5-medium", "gpt-5-low", "gpt-5-minimal"]
            else:
                models = ["gpt-5"]
            for m in models:
                all_models.append({"id": m, "object": "model", "owned_by": provider_name})
        elif provider_name == "grok":
            all_models.append({"id": "grok-beta", "object": "model", "owned_by": provider_name})
        elif provider_name == "openrouter":
            all_models.extend([
                {"id": "sonoma/sky", "object": "model", "owned_by": provider_name},
                {"id": "sonoma/dusk", "object": "model", "owned_by": provider_name},
            ])

    resp_data = {"object": "list", "data": all_models}
    resp = make_response(jsonify(resp_data), 200)
    for k, v in build_cors_headers().items():
        resp.headers.setdefault(k, v)
    return resp