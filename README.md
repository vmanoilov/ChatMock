<div align="center">
  <h1>ChatMock</h1>
  <p><b>The AI API that hijacks your browser sessions</b></p>
  <p>Turn your ChatGPT Plus, Grok, or other AI subscriptions into OpenAI-compatible APIs</p>
  <br>
</div>

# 🚀 What's New

## Latest - v1.5 [Security & Production Fixes]
**Date:** 2025-09-25

🔒 **Security hardening:** Bearer auth, CORS allowlists, HTTPS enforcement  
⚡ **Performance boost:** Rate limiting, concurrency controls, thread-safe metrics  
🔧 **Bug fixes:** Completed Qwen provider, fixed all placeholder code  
📚 **Better docs:** Security notes, complete environment variable reference  

[View full changelog →](#changelog)

# 🎭 What ChatMock Really Does

Think of ChatMock as a "digital impersonator" for your AI accounts. Here's the magic:

Instead of paying for expensive API access, ChatMock lets you use your existing ChatGPT Plus, Grok, or other AI subscriptions by masquerading as your browser. Your code thinks it's talking to the official OpenAI API, but behind the scenes, ChatMock is:

1. **Intercepting** your API requests
2. **Translating** them into browser-compatible formats  
3. **Hijacking** your logged-in browser session
4. **Fetching** responses from the actual AI service
5. **Converting** everything back to standard API format

It's like having a universal translator between your code and your AI subscriptions!

# 🔄 How It Works

```
Your Code/App ──→ ChatMock Proxy ──→ Browser Session ──→ ChatGPT/Grok/etc
      ↑                 ↑                    ↑
   Uses standard    Translates &         Real login
   OpenAI API      hijacks session      credentials
```

**The Flow:**
- Your app sends standard OpenAI API requests
- ChatMock receives them at `http://localhost:8000/v1/chat/completions`
- It authenticates using your saved browser cookies/tokens
- Makes requests to the actual AI service (ChatGPT, Grok, etc.)
- Streams back responses in OpenAI-compatible format

**Supported Providers:**
- **ChatGPT** - Uses your Plus/Pro browser session (no API key needed!)
- **Grok** - xAI's API with your API key
- **OpenRouter** - Sonoma models with 1M token context
- **Qwen** - Alibaba's AI with auth tokens

# ⚠️ Important Warnings

**🧪 This is an experimental hack!** Here's what you need to know:

- **Account Risk:** AI providers could theoretically detect this and close accounts
- **Breaking Changes:** Providers can (and will) change their systems, breaking ChatMock
- **Rate Limits:** Expect slower responses than official APIs
- **Educational Purpose:** This is a learning exercise and proof-of-concept
- **No Guarantees:** Use at your own risk - we're not responsible for any issues

**Why does this exist?**  
Pure curiosity and "what-if" thinking! It's fascinating to explore the boundaries between browser sessions and APIs. This project represents collaboration between human creativity and AI implementation.

# 🚀 Quick Start

## Mac Users

### 📱 GUI App (Easiest)
Download from [GitHub releases](https://github.com/vmanoilov/ChatMock/releases)

> **Note:** Since ChatMock isn't signed, run this to open:
> ```bash
> xattr -dr com.apple.quarantine /Applications/ChatMock.app
> ```

### 🍺 Homebrew (Command Line)
```bash
brew tap vmanoilov/chatmock
brew install chatmock
```

## Python Setup

1. **Clone & Install**
```bash
git clone https://github.com/vmanoilov/ChatMock.git
cd ChatMock
pip install -r requirements.txt
```

2. **Login to ChatGPT** (for ChatGPT provider)
```bash
python chatmock.py login
python chatmock.py info  # Verify it worked
```

3. **Start the Server**
```bash
python chatmock.py serve --provider chatgpt
# Server runs at http://127.0.0.1:8000
```

**Pro Tips:**
- Use `--provider grok`, `--provider openrouter`, or `--provider qwen` for other services
- Add `--model gpt-5` to set a default model
- Add `--reasoning-effort low` for faster ChatGPT responses

# 💻 Examples

## Python (OpenAI Library)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="anything"  # ignored for ChatGPT
)

response = client.chat.completions.create(
    model="gpt-5",
    messages=[{"role": "user", "content": "Hello! How does this work?"}]
)

print(response.choices[0].message.content)
```

## cURL
```bash
# ChatGPT
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role":"user","content":"Hello world!"}]
  }'

# Switch providers on-the-fly
curl "http://127.0.0.1:8000/v1/chat/completions?provider=qwen" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-max-preview",
    "messages": [{"role":"user","content":"Hi there!"}]
  }'
```

## JavaScript/Node.js
```javascript
const response = await fetch('http://127.0.0.1:8000/v1/chat/completions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'gpt-5',
    messages: [{ role: 'user', content: 'Hello ChatMock!' }]
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
```

# ⚙️ Configuration

## Environment Variables

### Provider Credentials
```bash
# For Grok
export XAI_API_KEY="your_xai_api_key"

# For OpenRouter
export OPENROUTER_API_KEY="your_openrouter_key"

# For Qwen
export QWEN_AUTH_TOKEN="your_bearer_token"
export QWEN_COOKIES="your_cookie_string"
```

### Server Settings
```bash
export CHATMOCK_PROVIDER="chatgpt"           # Default provider
export CHATMOCK_MODEL="gpt-5"                # Default model
export CHATMOCK_MAX_CONCURRENCY="1"          # Concurrent requests
export CHATMOCK_RATE_LIMIT_RPS="8"           # Requests per second
```

### Security (Production)
```bash
export CHATMOCK_REQUIRE_AUTH="true"          # Enable auth
export CHATMOCK_ACCESS_TOKEN="secret_token"  # API token
export CHATMOCK_CORS_ORIGINS="localhost:3000" # CORS allowlist
export REQUIRE_TLS="true"                    # Enforce HTTPS
```

## CLI Options

```bash
python chatmock.py serve --help

Options:
  --provider {chatgpt|grok|openrouter|qwen}  # Provider selection
  --model MODEL_NAME                         # Default model  
  --reasoning-effort {minimal|low|medium|high} # ChatGPT thinking level
  --reasoning-summary {auto|concise|detailed|none} # Summary style
  --expose-reasoning-models                  # Show reasoning variants
  --verbose                                  # Debug mode
```

# 🛠️ Technical Details

## Supported Features
- ✅ **Streaming responses** (real-time)
- ✅ **Tool/function calling** 
- ✅ **Vision/image understanding**
- ✅ **Reasoning summaries** (ChatGPT)
- ✅ **Multiple providers** in one API
- ✅ **Rate limiting** and concurrency control

## Models Available
- **ChatGPT:** `gpt-5` (plus reasoning variants if enabled)
- **Grok:** `grok-beta` 
- **OpenRouter:** `sonoma/sky`, `sonoma/dusk` (1M tokens)
- **Qwen:** `qwen3-max-preview`

View all: `GET http://127.0.0.1:8000/v1/models`

## Security & Limits
- **Message limits:** 64 messages max, 16k chars each
- **Token limit:** 2048 max tokens per request
- **Rate limiting:** Built-in queuing and timeout handling
- **Auth options:** Bearer tokens, CORS controls, HTTPS enforcement

## Testing
```bash
cd chatmock/tests
python test_chatgpt.py    # Requires login first
python test_grok.py       # Requires XAI_API_KEY
python test_openrouter.py # Requires OPENROUTER_API_KEY  
python test_qwen.py       # Requires QWEN_AUTH_TOKEN
```

# 📚 Changelog

## Original Work by RayBytes

**Full credit** to **RayBytes** ([@RayBytes](https://github.com/RayBytes/ChatMock)) for creating the core ChatMock project! His original work includes:

- Initial ChatGPT proxy implementation  
- OAuth authentication system
- Flask server foundation
- Reasoning and compatibility features
- Multi-provider architecture

## Fork Differences & Evolution

### v1.5 [Security & Production Fixes] - 2025-09-25

**🔒 Security Hardening:**
- Bearer authentication with backoff protection
- CORS allowlist (no more dangerous wildcards)
- HTTPS enforcement for production
- Input validation and message limits

**⚡ Performance & Reliability:**
- Thread-safe metrics and shared sessions
- Advanced rate limiting with fair queuing
- Automatic retry with exponential backoff
- Comprehensive error handling

**🔧 Bug Fixes & Quality:**
- Completed Qwen provider (no more placeholders!)
- Centralized configuration management
- Full pytest test suite
- Better logging and debugging

**Breaking Changes:**
- `CHATMOCK_CORS_ORIGINS` now requires explicit allowlist
- New security env vars: `CHATMOCK_REQUIRE_AUTH`, `REQUIRE_TLS`

### v1.4 [Qwen Provider] 
- Added Qwen API integration with auth token support
- Streaming response conversion for Qwen format
- Updated docs and tests

### v1.3 [Multi-Provider Support]
- Added Grok (xAI) and OpenRouter (Sonoma) providers
- Dynamic provider selection via `--provider` flag  
- Abstract provider base class for extensibility
- Individual provider test suites

### Earlier Versions
- Rate limiting and concurrency controls
- Ollama compatibility 
- Enhanced reasoning capabilities
- Docker support and GUI applications

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=vmanoilov/ChatMock&type=Timeline)](https://www.star-history.com/#vmanoilov/ChatMock&Timeline)

---

<div align="center">
  <p><i>🤖 Built with curiosity, powered by browser sessions</i></p>
  <p><b>Use responsibly • Educational purposes • At your own risk</b></p>
</div>

