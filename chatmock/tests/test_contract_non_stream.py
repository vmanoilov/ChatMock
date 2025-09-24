import pytest
from unittest.mock import Mock, patch
from chatmock.app import create_app
from chatmock.providers.qwen_client import QwenClient


@pytest.fixture
def app():
    app = create_app(provider="qwen", inject_base_prompt=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_qwen_non_stream_contract(mock_chat, client):
    # Mock the QwenClient.chat to return expected format
    mock_chat.return_value = {
        "text": "Hello, this is a test response.",
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
    }

    payload = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Say hello"}],
        "stream": False
    }

    response = client.post('/v1/chat/completions', json=payload)
    assert response.status_code == 200
    data = response.get_json()

    # Check OpenAI-style response structure
    assert "id" in data
    assert data["object"] == "chat.completion"
    assert "created" in data
    assert data["model"] == "qwen"
    assert "choices" in data
    assert len(data["choices"]) == 1
    choice = data["choices"][0]
    assert choice["index"] == 0
    assert "message" in choice
    assert choice["message"]["role"] == "assistant"
    assert choice["message"]["content"] == "Hello, this is a test response."
    assert choice["finish_reason"] == "stop"
    assert "usage" in data
    assert data["usage"]["prompt_tokens"] == 5
    assert data["usage"]["completion_tokens"] == 7
    assert data["usage"]["total_tokens"] == 12