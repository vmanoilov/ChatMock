import pytest
import time
from unittest.mock import patch
from chatmock.app import create_app


@pytest.fixture
def app():
    # Set low RPS for testing
    import os
    os.environ["CHATMOCK_RATE_LIMIT_RPS"] = "1"
    app = create_app(provider="qwen", inject_base_prompt=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_rate_limit_exceeded(mock_chat, client):
    # Mock successful response
    mock_chat.return_value = {"text": "OK", "usage": {}}

    payload = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Test"}],
        "stream": False
    }

    # First request should succeed
    response1 = client.post('/v1/chat/completions', json=payload)
    assert response1.status_code == 200

    # Second request immediately should be rate limited
    response2 = client.post('/v1/chat/completions', json=payload)
    assert response2.status_code == 429
    data = response2.get_json()
    assert data["error"]["type"] == "rate_limit"
    assert "retry_after" in data["error"]["details"]

    # Wait a bit and try again
    time.sleep(1.1)
    response3 = client.post('/v1/chat/completions', json=payload)
    assert response3.status_code == 200