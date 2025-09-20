# ChatMock Copilot Instructions

## Architecture Overview

ChatMock is a Flask-based proxy server that provides OpenAI-compatible API endpoints (`/v1/chat/completions`, `/v1/completions`, `/v1/models`) supporting multiple LLM providers. The core architecture consists of:

- **CLI Entry Point** (`chatmock.py`): Main command-line interface
- **Flask App** (`chatmock/app.py`): Web server with provider and Ollama blueprints
- **Provider Abstraction** (`chatmock/providers/`): Extensible provider system with base class
- **Rate Limiting** (`chatmock/rate_limit.py`): Concurrency control with fair queuing
- **OAuth Flow** (`chatmock/oauth.py`): ChatGPT authentication handling

## Key Components & Data Flow

### Provider System
- **Base Class** (`providers/base.py`): Abstract `Provider` with `send_message()` and `get_response()` methods
- **Provider Registry** (`providers/__init__.py`): `PROVIDERS` dict mapping names to instances
- **Request Flow**: `routes_providers.py` → provider selection → rate limiting → upstream call → response transformation

### Authentication Patterns
- **ChatGPT**: OAuth2 flow with local HTTP server (`oauth.py`, `utils.py`)
- **API Keys**: Environment variables (`XAI_API_KEY`, `OPENROUTER_API_KEY`)
- **Qwen**: Bearer token + cookies (`QWEN_AUTH_TOKEN`, `QWEN_COOKIES`)

### Response Processing
- **Streaming**: SSE translation (`utils.py`: `sse_translate_chat()`, `parse_qwen_stream()`)
- **Rate Limiting**: `Gate` class with permits and fair queuing
- **Error Handling**: Exponential backoff for 429s, structured error responses

## Critical Developer Workflows

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Authenticate with ChatGPT
python chatmock.py login

# Start development server
python chatmock.py serve --provider chatgpt --verbose

# Test specific provider
cd chatmock/tests && python test_qwen.py
```

### Docker Development
```bash
# Build and run
docker-compose up --build

# Login separately (different service)
docker-compose --profile login up chatmock-login
```

### Build Process
```bash
# Create distributable app
python build.py --platform macos  # or windows, linux
```

## Project-Specific Patterns

### Provider Implementation Pattern
```python
class NewProvider(Provider):
    def send_message(self, model, messages, stream=True, **kwargs):
        # Auth setup
        headers = self._build_headers()
        payload = self._build_payload(model, messages, **kwargs)

        # Request with retry logic
        return self._retry_request(lambda: requests.post(URL, headers=headers, json=payload, stream=stream))

    def get_response(self, model, messages, **kwargs):
        upstream, error = self.send_message(model, messages, stream=False, **kwargs)
        return self._parse_response(upstream)
```

### Configuration Hierarchy
1. **CLI Flags**: Override defaults (`--provider`, `--model`, `--reasoning-effort`)
2. **Environment Variables**: `CHATMOCK_PROVIDER`, `XAI_API_KEY`, etc.
3. **Request Parameters**: `?provider=grok` in API calls
4. **Defaults**: Hardcoded fallbacks

### Error Response Pattern
```python
def handle_error(message, status=400):
    resp = make_response(jsonify({"error": {"message": message}}), status)
    resp.headers.update(build_cors_headers())
    return resp
```

### Rate Limiting Integration
```python
try:
    permit = gate.acquire(wait_timeout=queue_timeout_seconds)
    # ... make upstream request ...
finally:
    permit.release()
```

### Model Normalization Pattern
```python
def normalize_model_name(name: str | None, debug_model: str | None = None) -> str:
    if isinstance(debug_model, str) and debug_model.strip():
        return debug_model.strip()
    if not isinstance(name, str) or not name.strip():
        return "gpt-5"
    # Strip reasoning effort suffixes (-minimal, -low, -medium, -high)
    base = name.split(":", 1)[0].strip()
    for sep in ("-", "_"):
        lowered = base.lower()
        for effort in ("minimal", "low", "medium", "high"):
            suffix = f"{sep}{effort}"
            if lowered.endswith(suffix):
                base = base[: -len(suffix)]
                break
    # Apply model mapping
    mapping = {
        "gpt5": "gpt-5",
        "gpt-5-latest": "gpt-5",
        "codex": "codex-mini-latest",
    }
    return mapping.get(base, base)
```

### Reasoning Integration Pattern
```python
def build_reasoning_param(
    base_effort: str = "medium", base_summary: str = "auto", overrides: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    effort = (base_effort or "").strip().lower()
    summary = (base_summary or "").strip().lower()
    
    # Apply overrides from request
    if isinstance(overrides, dict):
        o_eff = str(overrides.get("effort", "")).strip().lower()
        o_sum = str(overrides.get("summary", "")).strip().lower()
        if o_eff in valid_efforts and o_eff:
            effort = o_eff
        if o_sum in valid_summaries and o_sum:
            summary = o_sum
    
    reasoning: Dict[str, Any] = {"effort": effort}
    if summary != "none":
        reasoning["summary"] = summary
    return reasoning
```

### Data Transformation Pattern
```python
def to_data_url(image_str: str) -> str:
    if not isinstance(image_str, str) or not image_str:
        return image_str
    s = image_str.strip()
    if s.startswith("data:image/"):
        return s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # Convert base64 to data URL with MIME type detection
    b64 = s.replace("\n", "").replace("\r", "")
    kind = "image/png"
    if b64.startswith("/9j/"):
        kind = "image/jpeg"
    elif b64.startswith("iVBORw0KGgo"):
        kind = "image/png"
    elif b64.startswith("R0lGOD"):
        kind = "image/gif"
    return f"data:{kind};base64,{b64}"
```

## Testing Conventions

### Provider Tests
- **Location**: `chatmock/tests/test_{provider}.py`
- **Pattern**: Direct provider instantiation, mock responses for parsing tests
- **Requirements**: Real API credentials for integration tests
- **Execution**: `cd chatmock/tests && python test_qwen.py`

### Key Test Files
- `test_chatgpt.py`: OAuth and ChatGPT API integration
- `test_grok.py`: xAI API with streaming
- `test_openrouter.py`: Sonoma models with truncation
- `test_qwen.py`: Qwen API with auth tokens and cookies

## Build & Deployment

### PyInstaller Build
- **Script**: `build.py` with platform-specific icon generation
- **Output**: Standalone executables with bundled Python environment
- **Icons**: PNG → platform-specific formats (.icns, .ico)

### Docker Deployment
- **Multi-stage**: Login service separate from main API service
- **Volumes**: Persistent auth data in `/data`
- **Health Checks**: HTTP endpoint monitoring
- **Environment**: `.env` file for secrets

## Common Integration Points

### Adding New Providers
1. Create `providers/new_provider.py` extending `Provider`
2. Add to `PROVIDERS` dict in `providers/__init__.py`
3. Update CLI choices in `cli.py`
4. Add environment variables to README
5. Create `tests/test_new_provider.py`

### Extending API Endpoints
1. Add routes to `routes_providers.py` or create new blueprint
2. Register blueprint in `app.py`
3. Apply rate limiting and CORS headers
4. Handle provider selection and parameter extraction

### Authentication Extensions
1. Follow OAuth pattern in `oauth.py` for interactive auth
2. Use environment variables for API keys
3. Implement token refresh logic if needed
4. Add to `utils.py` auth helpers

## Code Quality Patterns

### Logging
- Use `logger = logging.getLogger(__name__)` in all modules
- Sanitize sensitive data: `sanitize_log_message()` for tokens/cookies
- Structured error logging with status codes and response bodies

### Error Handling
- Flask error responses with CORS headers
- Upstream error propagation with status code mapping
- Graceful degradation for missing credentials

### Configuration Management
- Environment-first approach with sensible defaults
- Runtime config storage in Flask `app.config`
- CLI flag precedence over environment variables

## Debugging Tips

### Verbose Mode
```bash
python chatmock.py serve --verbose
```
Shows request/response bodies, streaming chunks, and upstream errors.

### Provider-Specific Debugging
- **ChatGPT**: Check OAuth tokens with `python chatmock.py info`
- **API Providers**: Verify environment variables are set
- **Streaming**: Use verbose mode to inspect SSE chunks

### Common Issues
- **429 Errors**: Check rate limiting config (`CHATMOCK_MAX_CONCURRENCY`)
- **Auth Failures**: Re-run `python chatmock.py login` for ChatGPT
- **CORS Issues**: Ensure `build_cors_headers()` is applied to all responses

## File Organization Reference

```
chatmock/
├── app.py              # Flask app factory
├── cli.py              # Command-line interface
├── config.py           # Constants and base instructions
├── providers/          # Provider implementations
│   ├── base.py        # Abstract provider class
│   ├── qwen.py        # Qwen provider
│   └── __init__.py    # Provider registry
├── routes_providers.py # OpenAI-compatible endpoints
├── rate_limit.py       # Concurrency control
├── oauth.py           # ChatGPT authentication
├── utils.py           # Shared utilities
└── tests/             # Provider-specific tests
```

### File Organization Conventions
- **CLI Commands**: `cli.py` with `cmd_*` functions for each subcommand
- **Route Handlers**: `routes_*.py` with blueprint registration in `app.py`
- **Provider Tests**: `tests/test_{provider}.py` pattern
- **Utility Functions**: `utils.py` for shared helpers across modules
- **Configuration**: `config.py` for constants and base instructions

### Naming Conventions
- **Environment Variables**: `CHATMOCK_*`, `QWEN_*`, `XAI_*`, `OPENROUTER_*` prefixes
- **CLI Flags**: `--{provider}`, `--{model}`, `--{reasoning-effort}` patterns
- **Function Names**: `build_*`, `convert_*`, `parse_*`, `handle_*` prefixes for utilities
- **Error Handling**: `handle_error()` pattern with CORS headers and status codes