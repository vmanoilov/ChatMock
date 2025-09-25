<div align="center">
  <h1>ChatMock</h1>
  <p><b>Multi-provider OpenAI & Ollama compatible API.</b></p>
  <p>Supports ChatGPT, Grok (xAI), OpenRouter (Sonoma models), and Qwen with OpenAI-compatible endpoints.</p>
  <br>
</div>

## What It Does

ChatMock runs a local server providing OpenAI-compatible API endpoints (/v1/chat/completions, /v1/completions, /v1/models) and Ollama compatibility. It supports multiple LLM providers:

- **ChatGPT**: Uses your authenticated ChatGPT Plus/Pro account (no API key needed, requires login)
- **Grok**: xAI Grok API integration (requires XAI_API_KEY environment variable)
- **OpenRouter**: Sonoma Sky/Dusk models via OpenRouter (requires OPENROUTER_API_KEY, supports 1M token context with truncation)
- **Qwen**: Qwen API integration (requires QWEN_AUTH_TOKEN and QWEN_COOKIES environment variables)

Provider selection via CLI `--provider` flag or request query parameter. All providers support streaming and tool calling where applicable.

## Quickstart

### Mac Users

#### GUI Application

If you're on **macOS**, you can download the GUI app from the [GitHub releases](https://github.com/vmanoilov/ChatMock/releases).  
> **Note:** Since ChatMock isn't signed with an Apple Developer ID, you may need to run the following command in your terminal to open the app:
>
> ```bash
> xattr -dr com.apple.quarantine /Applications/ChatMock.app
> ```
>
> *[More info here.](https://github.com/deskflow/deskflow/wiki/Running-on-macOS)*

#### Command Line (Homebrew)

You can also install ChatMock as a command-line tool using [Homebrew](https://brew.sh/):
```
brew tap vmanoilov/chatmock
brew install chatmock
```

### Python
If you wish to just simply run this as a python flask server, you are also freely welcome too.

Clone or download this repository, then cd into the project directory. Then follow the instrunctions listed below.

1. Sign in with your ChatGPT account and follow the prompts
```bash
python chatmock.py login
```
You can make sure this worked by running `python chatmock.py info`

2. After the login completes successfully, you can just simply start the local server

```bash
python chatmock.py serve --provider chatgpt
```
Use `--provider grok`, `--provider openrouter`, or `--provider qwen` for other providers. Add `--model gpt-5` (or grok-beta, sonoma/sky, qwen3-max-preview) to set default model.

The server runs at http://127.0.0.1:8000 by default.

**Reminder:** For OpenAI-compatible endpoints, use /v1/ (e.g., http://127.0.0.1:8000/v1/chat/completions). Specify `?provider=grok` or `?provider=qwen` in requests to override default provider.

# Examples

### Python 

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="key"  # ignored
)

resp = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "hello world"}]
)

print(resp.choices[0].message.content)
```

### curl

```bash
# ChatGPT
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role":"user","content":"hello world"}]
  }'

# Qwen
curl "http://127.0.0.1:8000/v1/chat/completions?provider=qwen&chat_id=" \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-max-preview",
    "messages": [{"role":"user","content":"hello world"}]
  }'
```

# What's supported

- Tool calling
- Vision/Image understanding
- Thinking summaries (through thinking tags)

## Security & Limits

### Authentication & Authorization
- **Bearer Auth**: Set `CHATMOCK_REQUIRE_AUTH=true` and `CHATMOCK_ACCESS_TOKEN` for API access control.
- **CORS**: `CHATMOCK_CORS_ORIGINS` should be a comma-separated allowlist (never `*` in production).
- **HTTPS**: Production deployments must run behind TLS (nginx/traefik). Set `REQUIRE_TLS=true` to enforce.

### Input Validation
- **Model Allowlist**: Requests validate models per provider (e.g., Qwen: `qwen`, `qwen3-max-preview`).
- **Message Limits**: Max 64 messages, 16k chars per message, 256k total bytes.
- **Token Clamping**: `max_tokens` capped at 2048.

### Rate Limiting
- Built-in concurrency control and RPS limiting to prevent abuse.
- Queue with timeout; excess requests return 429 with Retry-After.

## Notes & Limits

- Requires an active, paid ChatGPT account.
- Expect lower rate limits than what you may recieve in the ChatGPT app.
- Some context length might be taken up by internal instructions (but they dont seem to degrade the model)
- Use responsibly and at your own risk. This project is not affiliated with OpenAI, and is a educational exercise.

## Supported Models

- **ChatGPT**: gpt-5 (with reasoning variants: gpt-5-high, gpt-5-medium, gpt-5-low, gpt-5-minimal if --expose-reasoning-models)
- **Grok**: grok-beta (Code Fast 1)
- **OpenRouter**: sonoma/sky, sonoma/dusk (1M token context)
- **Qwen**: qwen3-max-preview

View available models: GET /v1/models

## Configuration

### Environment Variables

- `XAI_API_KEY`: For Grok provider
- `OPENROUTER_API_KEY`: For OpenRouter Sonoma provider
- `QWEN_AUTH_TOKEN`: For Qwen provider (Bearer token)
- `QWEN_COOKIES`: For Qwen provider (full cookie string)
- `QWEN_CHAT_ID`: Optional for Qwen provider (defaults to demo ID)
- `CHATMOCK_PROVIDER`: Default provider (chatgpt|grok|openrouter|qwen)
- `CHATMOCK_MODEL`: Default model if not specified in requests
- `CHATMOCK_REQUIRE_AUTH`: Enable bearer auth (true/false)
- `CHATMOCK_ACCESS_TOKEN`: Bearer token for auth
- `CHATMOCK_CORS_ORIGINS`: Comma-separated CORS allowlist
- `REQUIRE_TLS`: Enforce HTTPS (true/false)
- `CHATMOCK_RATE_LIMIT_RPS`: RPS limit (default 8)
- `CHATMOCK_MAX_CONCURRENCY`: Max concurrent requests (default 1)
- `CHATMOCK_QUEUE_LIMIT`: Max queued requests (default 100)
- `CHATMOCK_QUEUE_TIMEOUT`: Queue timeout seconds (default 120)
- `INJECT_BASE_PROMPT`: Inject base system prompt (true/false)

### CLI Options

- `--provider {chatgpt|grok|openrouter|qwen}`: Select default provider
- `--model {model_name}`: Set default model
- `--reasoning-effort {minimal|low|medium|high}`: ChatGPT reasoning level
- `--reasoning-summary {auto|concise|detailed|none}`: Summary verbosity
- `--expose-reasoning-models`: List reasoning variants in /v1/models

## Testing Providers

Run individual provider tests (requires credentials):

```bash
cd chatmock/tests
python test_chatgpt.py  # After login
python test_grok.py     # Set XAI_API_KEY
python test_openrouter.py  # Set OPENROUTER_API_KEY
python test_qwen.py     # Set QWEN_AUTH_TOKEN and QWEN_COOKIES
```

### Thinking effort

- `--reasoning-effort` (choice of minimal,low,medium,high)<br>
GPT-5 has a configurable amount of "effort" it can put into thinking, which may cause it to take more time for a response to return, but may overall give a smarter answer. Applying this parameter after `serve` forces the server to use this reasoning effort by default, unless overrided by the API request with a different effort set. The default reasoning effort without setting this parameter is `medium`.

### Thinking summaries

- `--reasoning-summary` (choice of auto,concise,detailed,none)<br>
Models like GPT-5 do not return raw thinking content, but instead return thinking summaries. These can also be customised by you.

### Rate Limiting

ChatMock includes built-in rate limiting to manage concurrent requests and prevent server overload.

- `CHATMOCK_MAX_CONCURRENCY`: Maximum number of simultaneous upstream requests (default: 1)
- `CHATMOCK_QUEUE_LIMIT`: Maximum number of queued requests before rejecting with 429 (default: 100)
- `CHATMOCK_QUEUE_TIMEOUT_S`: Timeout in seconds for acquiring a permit from the queue (default: 60)

When the server is busy, requests will be queued fairly or rejected with a 429 status and Retry-After header. The system also includes automatic retry with exponential backoff for upstream 429 errors.

## Notes
If you wish to have the fastest responses, I'd recommend setting `--reasoning-effort` to low, and `--reasoning-summary` to none.
All parameters and choices can be seen by sending `python chatmock.py serve --h`<br>
The context size of this route is also larger than what you get access to in the regular ChatGPT app.

**When the model returns a thinking summary, the model will send back thinking tags to make it compatible with chat apps. If you don't like this behavior, you can instead set `--reasoning-compat` to legacy, and reasoning will be set in the reasoning tag instead of being returned in the actual response text.**

## Testing

Sample tests in `chatmock/tests/` verify each provider works independently.

# Changelog

## Original Work by Vladislav Manoilov (vmanoilov)

The core ChatMock project was created by **Vladislav Manoilov** (GitHub: [@vmanoilov](https://github.com/vmanoilov)). His original work includes:

- Initial ChatGPT proxy implementation
- OAuth authentication system
- Basic Flask server setup
- Reasoning and compatibility features
- Multi-provider foundation

**Original work ends here.** All subsequent changes and fixes are contributions from the current maintainer.

---

## Continued Development - v1.5 [Security & Production Fixes]

**Date:** 2025-09-25
**Maintainer:** Current maintainer (Kilo Code implementation)

This version focuses on production hardening, security improvements, and completing incomplete features for the Qwen provider.

### Key Changes:
- **Completed Qwen Provider Implementation**: Fixed placeholders, added shared sessions, proper error handling
- **Security Enhancements**: Bearer auth with backoff, CORS allowlist, HTTPS enforcement, input validation
- **Performance & Reliability**: Thread-safe metrics, rate limiting with concurrency control, error normalization
- **Code Quality**: Centralized config, removed magic numbers, comprehensive tests
- **Documentation**: Updated README with security notes, limits, and full env var reference

### Technical Details:
- Replaced all `...` placeholders with working code
- Added input limits: 64 messages max, 16k chars/message, 256k total bytes, 2048 max tokens
- Implemented auth failure backoff (5 attempts/minute per IP)
- Thread-safe metrics with locking
- Comprehensive pytest suite for all features
- Smoke script for automated testing

### Files Modified:
- `chatmock/providers/qwen_client.py`: Updated with shared Session, proper auth
- `chatmock/routes_providers.py`: Added validation, auth, HTTPS checks
- `chatmock/config.py`: Centralized limits and defaults
- `chatmock/app.py`: Thread-safe metrics
- `README.md`: Security docs, env vars
- All test files: Enhanced coverage

### Breaking Changes:
- `CHATMOCK_CORS_ORIGINS` now requires explicit allowlist (no default `*`)
- New required env vars for security: `CHATMOCK_REQUIRE_AUTH`, `REQUIRE_TLS`

### Previous Versions:

- [v1.4] [Qwen] Added Qwen provider support
  - Added `chatmock/providers/qwen.py`: QwenProvider class with API integration, headers, auth, and streaming conversion
  - Updated `chatmock/providers.py`: Added Qwen to PROVIDERS dict
  - Updated `chatmock/routes_providers.py`: Added Qwen-specific handling for streaming and models
  - Updated README: Documented Qwen provider, env vars, curl examples, and tests

- [v1.3] [Sonoma] Multi-provider support (ChatGPT, Grok, OpenRouter Sonoma)
  - Added `providers.py`: Abstract Provider base class with ChatGPTProvider (wraps existing logic), GrokProvider (xAI API), OpenRouterProvider (Sonoma models with truncation)
  - Added `routes_providers.py`: Dynamic provider selection for OpenAI endpoints
  - Updated `cli.py`: --provider and --model flags
  - Updated `app.py`: Register providers_bp, store config
  - Added `tests/`: test_chatgpt.py, test_grok.py, test_openrouter.py
  - Enhanced logging for exceptions throughout providers
  - Updated README: Document new providers, config, tests

Previous changes...

# Changelog

- [main] [vladislav manoilov] Add rate limiting and concurrency control, update README
  - Added `chatmock/rate_limit.py`: Implements a fair concurrency gate to limit simultaneous upstream requests, with configurable queue limits and timeouts to prevent server overload.
  - Updated `chatmock/routes_openai.py`: Integrated rate limiting with permit acquisition/release, added automatic retry with exponential backoff for upstream 429 errors to handle rate limits gracefully.
  - Updated README.md: Added documentation for new rate limiting environment variables and behavior.
  - Deleted `prompt.md`: Removed unused prompt file.
  - Reasoning: Improves stability and reliability by managing concurrent requests and handling upstream rate limits, preventing crashes and improving user experience under load. Cleanup of unused files.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=vmanoilov/ChatMock&type=Timeline)](https://www.star-history.com/#vmanoilov/ChatMock&Timeline)

