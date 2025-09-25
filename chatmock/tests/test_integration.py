import pytest
from unittest.mock import patch
from chatmock.app import create_app


@pytest.fixture
def app():
    app = create_app(provider="qwen", inject_base_prompt=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_qwen_full_integration_non_stream(mock_chat, client):
    """Test full integration for Qwen non-streaming request."""
    # Mock the QwenClient.chat to return expected format
    mock_chat.return_value = {
        "text": "Hello, this is a test response.",
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
    }

    payload = {
        "model": "qwen3-max-preview",
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
    assert data["model"] == "qwen3-max-preview"
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


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_qwen_full_integration_stream(mock_chat, client):
    """Test full integration for Qwen streaming request."""
    # Mock the QwenClient.chat to return a generator yielding chunks and "stop"
    def mock_generator():
        yield "Hello"
        yield " world"
        yield "stop"

    mock_chat.return_value = mock_generator()

    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Stream me"}],
        "stream": True
    }

    response = client.post('/v1/chat/completions', json=payload)
    assert response.status_code == 200
    assert response.content_type == "text/event-stream"

    # Collect all data lines
    data_lines = []
    for line in response.data.decode('utf-8').split('\n'):
        if line.startswith("data: "):
            data_lines.append(line[6:])

    # Should have at least 2 data lines: content chunks + finish
    assert len(data_lines) >= 2

    # Check first content chunk
    import json
    first_chunk = json.loads(data_lines[0])
    assert "id" in first_chunk
    assert first_chunk["object"] == "chat.completion.chunk"
    assert "created" in first_chunk
    assert first_chunk["model"] == "qwen3-max-preview"
    assert "choices" in first_chunk
    assert len(first_chunk["choices"]) == 1
    choice = first_chunk["choices"][0]
    assert choice["index"] == 0
    assert "delta" in choice
    assert "content" in choice["delta"]
    assert choice["finish_reason"] is None

    # Check last chunk is finish
    last_chunk = json.loads(data_lines[-2])  # Before [DONE]
    assert last_chunk["choices"][0]["delta"] == {}
    assert last_chunk["choices"][0]["finish_reason"] == "stop"

    # Check ends with [DONE]
    assert data_lines[-1] == "[DONE]"