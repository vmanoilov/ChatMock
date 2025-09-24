import pytest
from unittest.mock import patch
from chatmock.app import create_app
from chatmock.config import BASE_INSTRUCTIONS


@pytest.fixture
def app_with_injection():
    app = create_app(provider="qwen", inject_base_prompt=True)
    return app


@pytest.fixture
def app_without_injection():
    app = create_app(provider="qwen", inject_base_prompt=False)
    return app


@pytest.fixture
def client_with_injection(app_with_injection):
    return app_with_injection.test_client()


@pytest.fixture
def client_without_injection(app_without_injection):
    return app_without_injection.test_client()


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_base_prompt_injection_with_user_system(mock_chat, client_with_injection):
    # When user provides system message, do not inject base prompt
    mock_chat.return_value = {"text": "Response", "usage": {}}

    payload = {
        "model": "qwen3-max-preview",
        "messages": [
            {"role": "system", "content": "User system prompt"},
            {"role": "user", "content": "Hello"}
        ],
        "stream": False
    }

    client_with_injection.post('/v1/chat/completions', json=payload)

    # Check that chat was called with messages as-is (no base prompt prepended)
    args, kwargs = mock_chat.call_args
    messages = kwargs['messages']
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "User system prompt"


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_base_prompt_injection_without_user_system(mock_chat, client_with_injection):
    # When no user system message, inject base prompt
    mock_chat.return_value = {"text": "Response", "usage": {}}

    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }

    client_with_injection.post('/v1/chat/completions', json=payload)

    # Check that base prompt was prepended
    args, kwargs = mock_chat.call_args
    messages = kwargs['messages']
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == BASE_INSTRUCTIONS
    assert messages[1]["role"] == "user"


@patch('chatmock.providers.qwen_client.QwenClient.chat')
def test_no_injection_when_disabled(mock_chat, client_without_injection):
    # When injection disabled, never inject
    mock_chat.return_value = {"text": "Response", "usage": {}}

    payload = {
        "model": "qwen3-max-preview",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    }

    client_without_injection.post('/v1/chat/completions', json=payload)

    # Check that no system message was added
    args, kwargs = mock_chat.call_args
    messages = kwargs['messages']
    assert len(messages) == 1
    assert messages[0]["role"] == "user"