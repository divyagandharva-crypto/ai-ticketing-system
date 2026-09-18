"""
Standalone script to test whether the Anthropic API key in .env is valid,
completely independent of FastAPI, curl, or PowerShell quoting issues.
"""
from app.config import settings
from anthropic import Anthropic

print(f"Key starts with: {settings.anthropic_api_key[:15]}...")
print(f"Key length: {len(settings.anthropic_api_key)}")

client = Anthropic(api_key=settings.anthropic_api_key)

try:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=10,
        messages=[{"role": "user", "content": "hi"}]
    )
    print("SUCCESS:", response.content[0].text)
except Exception as e:
    print("FAILED:", e)