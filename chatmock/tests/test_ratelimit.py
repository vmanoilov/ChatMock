import pytest
import time
import threading
from unittest.mock import patch
from chatmock.app import create_app
from chatmock.rate_limit import Gate, TokenBucket


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
        "model": "qwen3-max-preview",
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


def test_queue_full():
    """Test that queue limits are enforced."""
    gate = Gate(max_concurrency=1, queue_limit=1)  # Only 1 in queue

    # Acquire first permit
    p1 = gate.acquire()
    assert p1 is not None

    # Start a thread that will wait in queue
    results = []
    def waiter():
        try:
            p = gate.acquire(wait_timeout=0.1)
            results.append('acquired')
            p.release()
        except Exception as e:
            results.append(str(type(e).__name__))

    t = threading.Thread(target=waiter)
    t.start()
    t.join()  # Wait for thread to finish

    # Should have acquired since queue allows 1
    assert results == ['acquired']

    # Now queue is full, next should fail
    try:
        gate.acquire(wait_timeout=0.1)
        assert False, "Should have raised GateBusy"
    except Exception as e:
        assert 'GateBusy' in str(type(e))

    p1.release()  # Release to allow cleanup


def test_token_bucket_rate_limit():
    """Test TokenBucket rate limiting."""
    bucket = TokenBucket(rate_per_second=2, burst=2)

    # Should acquire initial burst
    assert bucket.acquire(2) == True
    assert bucket.tokens == 0

    # Should fail immediately
    assert bucket.acquire(1) == False

    # Wait for tokens to regenerate
    time.sleep(0.6)  # Should regenerate ~1.2 tokens

    # Should acquire 1
    assert bucket.acquire(1) == True
    assert bucket.tokens < 1  # Should have used the token