import anthropic
import json
from app.config import settings
api_key = settings.anthropic_api_key

message = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": """Given this support ticket, respond with ONLY the raw JSON object, no markdown formatting, no code fences, no backticks, no explanation. Just the JSON itself starting with { and ending with }.

Format:
{"category": "bug|feature-request|question", "urgency": "low|medium|high", "summary": "one sentence"}

Ticket: Login page shows blank screen, user reports it happens on Chrome only, started after yesterday's deploy."""
        }
    ]
)

response_text = message.content[0].text

if response_text.startswith("```"):
    response_text = response_text.split("```")[1]
    if response_text.startswith("json"):
        response_text = response_text[4:]
    response_text = response_text.strip()

data = json.loads(response_text)

print("Category:", data["category"])
print("Urgency:", data["urgency"])
print("Summary:", data["summary"])