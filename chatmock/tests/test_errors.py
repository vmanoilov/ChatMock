import pytest
from unittest.mock import patch
from chatmock.app import create_app
from chatmock.providers.qwen_client import ChatMockError


@pytest.fixture
def app():
    app = create_app(provider="qwen", inject_base_prompt=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_upstream_error_mapping(mock_chat, client):
    # Mock ChatMockError from client
    mock_chat.side_effect = ChatMockError("upstream", 502, "Upstream service error", retry_after=5)

    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Test"}],
        "stream": False
    }

    response = client.post('/v1/chat/completions', json=payload)
    assert response.status_code == 502
    data = response.get_json()
    assert data["error"]["type"] == "upstream"
    assert data["error"]["message"] == "Upstream service error"
    assert data["error"]["details"]["retry_after"] == 5
    assert data["error"]["details"]["upstream_status"] == 502


def test_invalid_json_error(client):
    response = client.post('/v1/chat/completions', data="invalid json")
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["type"] == "bad_request"
    assert "Invalid JSON" in data["error"]["message"]


def test_missing_messages_error(client):
    payload = {"model": "qwen3-max-preview"}
    response = client.post('/v1/chat/completions', json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["type"] == "bad_request"
    assert "messages" in data["error"]["message"]


def test_invalid_chat_id_error(client):
    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Test"}],
        "stream": False
    }
    response = client.post('/v1/chat/completions?chat_id=invalid-uuid', json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["type"] == "bad_request"
    assert "chat_id" in data["error"]["message"]


@patch('chatmock.routes_providers.check_auth')
def test_auth_error(mock_check_auth, client):
    mock_check_auth.return_value = {"error": {"type": "bad_request", "message": "Auth failed"}}

    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Test"}],
        "stream": False
    }

    response = client.post('/v1/chat/completions', json=payload)
    assert response.status_code == 400  # Assuming handle_error returns 400 for auth
    data = response.get_json()
    assert data["error"]["message"] == "Auth failed"