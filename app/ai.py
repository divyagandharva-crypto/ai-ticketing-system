import anthropic
import json
from .config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def analyze_ticket(title: str, description: str):
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""Given this support ticket, respond with ONLY the raw JSON object, no markdown formatting, no code fences, no backticks, no explanation. Just the JSON itself starting with {{ and ending with }}.

Format:
{{"category": "bug|feature-request|question", "urgency": "low|medium|high", "summary": "one sentence"}}

Ticket title: {title}
Ticket description: {description}"""
            }
        ]
    )

    response_text = message.content[0].text
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()

    return json.loads(response_text)


def suggest_resolution(title: str, description: str, similar_tickets: list):
    """
    RAG generation step: given a ticket and a list of similar past tickets
    (retrieved via pgvector cosine similarity), ask Claude to draft a
    suggested resolution grounded in how those similar tickets were handled.

    similar_tickets is expected to be a list of dicts/objects with at least
    title, description, and status (add resolution/comments text here too,
    once that's tracked, for stronger grounding).
    """
    if similar_tickets:
        context_blocks = "\n\n".join(
            f"""Similar past ticket:
Title: {t['title']}
Description: {t['description']}
Status: {t['status']}"""
            for t in similar_tickets
        )
    else:
        context_blocks = "No similar past tickets were found."

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""You are helping a support agent resolve a new ticket. Respond with ONLY the raw JSON object, no markdown formatting, no code fences, no backticks, no explanation. Just the JSON itself starting with {{ and ending with }}.

Format:
{{"suggested_resolution": "2-4 sentence suggested next steps or fix", "confidence": "low|medium|high", "based_on_similar_tickets": true|false}}

New ticket title: {title}
New ticket description: {description}

Context from similar past tickets:
{context_blocks}"""
            }
        ]
    )

    response_text = message.content[0].text
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()

    return json.loads(response_text)