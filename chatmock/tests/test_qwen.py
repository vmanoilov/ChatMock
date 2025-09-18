import os
import unittest.mock
from chatmock.providers import QwenProvider
from chatmock.providers.qwen import parse_qwen_stream

def test_qwen():
    """Test Qwen provider. Requires QWEN_AUTH_TOKEN and QWEN_COOKIES environment variables."""
    auth_token = os.getenv("QWEN_AUTH_TOKEN")
    cookies = os.getenv("QWEN_COOKIES")
    if not auth_token or not cookies:
        print("ERROR: QWEN_AUTH_TOKEN and/or QWEN_COOKIES environment variables not set.")
        return

    provider = QwenProvider()
    messages = [{"role": "user", "content": "Hello, what is Qwen?"}]
    try:
        response = provider.get_response("qwen", messages)
        print("Qwen Response:", response["content"])
    except Exception as e:
        print("Qwen Test Error:", str(e))

def test_qwen_streaming():
    """Test Qwen streaming parsing."""
    # Mock response with Qwen-like stream data
    mock_response = unittest.mock.Mock()
    mock_response.iter_lines.return_value = [
        b'data: {"content": "Hello", "finished": false}\n\n',
        b'data: {"content": " world", "finished": false}\n\n',
        b'data: {"content": "", "finished": true}\n\n',
    ]

    chunks = list(parse_qwen_stream(mock_response, "qwen", 1234567890))
    print(f"Generated {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i}: {chunk.decode('utf-8', errors='ignore')[:100]}...")

    # Check for expected structure
    assert len(chunks) >= 3  # content chunks + finish + DONE
    assert b'"finish_reason": "stop"' in chunks[-2]  # finish chunk
    assert chunks[-1] == b"data: [DONE]\n\n"

if __name__ == "__main__":
    test_qwen()
    test_qwen_streaming()