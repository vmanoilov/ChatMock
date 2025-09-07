import os
from chatmock.providers import OpenRouterProvider

def test_openrouter():
    """Test OpenRouter provider. Requires OPENROUTER_API_KEY environment variable."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: No OPENROUTER_API_KEY environment variable set.")
        return

    provider = OpenRouterProvider()
    messages = [{"role": "user", "content": "Hello, what is Sonoma?"}]
    try:
        response = provider.get_response("sonoma/sky", messages)
        print("OpenRouter Sonoma Response:", response["content"])
    except Exception as e:
        print("OpenRouter Test Error:", str(e))

if __name__ == "__main__":
    test_openrouter()