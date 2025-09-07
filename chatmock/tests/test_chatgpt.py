from chatmock.providers import ChatGPTProvider
from chatmock.utils import get_effective_chatgpt_auth

def test_chatgpt():
    """Test ChatGPT provider. Run after login to store tokens."""
    access_token, account_id = get_effective_chatgpt_auth()
    if not access_token or not account_id:
        print("ERROR: No ChatGPT credentials. Run 'python -m chatmock login' first.")
        return

    provider = ChatGPTProvider()
    messages = [{"role": "user", "content": "Hello, what is ChatMock?"}]
    try:
        response = provider.get_response("gpt-5", messages)
        print("ChatGPT Response:", response["content"])
    except Exception as e:
        print("ChatGPT Test Error:", str(e))

if __name__ == "__main__":
    test_chatgpt()