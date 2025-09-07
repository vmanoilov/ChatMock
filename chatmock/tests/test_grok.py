import os
from chatmock.providers import GrokProvider

def test_grok():
    """Test Grok provider. Requires XAI_API_KEY environment variable."""
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("ERROR: No XAI_API_KEY environment variable set.")
        return

    provider = GrokProvider()
    messages = [{"role": "user", "content": "Hello, what is Grok?"}]
    try:
        response = provider.get_response("grok-beta", messages)
        print("Grok Response:", response["content"])
    except Exception as e:
        print("Grok Test Error:", str(e))

if __name__ == "__main__":
    test_grok()