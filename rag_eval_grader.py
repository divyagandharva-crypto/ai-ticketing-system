"""
RAG Eval Grader

Runs all 50 questions in rag_eval_qa_full.py against the live /agent/chat
endpoint, then uses Claude as a judge to grade each actual answer against
its expected_answer + grading_notes.

This is the "known correct answer" RAG eval — distinct from eval_harness.py,
which checks structural behavior (does retrieval return the right cluster,
does tool selection pick the right tool). This checks answer QUALITY: is
the actual generated answer factually and behaviorally correct.

Usage:
    Set your JWT token as an environment variable before running:
        (Windows PowerShell)  $env:TEST_JWT_TOKEN="your-fresh-token"
        (bash/WSL)             export TEST_JWT_TOKEN="your-fresh-token"
    Then:
        python rag_eval_grader.py

Requires: pip install requests anthropic
Reads your Anthropic API key the same way your app does - from the
ANTHROPIC_API_KEY environment variable (matches your app's config.py
pattern of reading secrets from env, not hardcoding them).
"""

import json
import os
import sys
import time

import requests
from anthropic import Anthropic

from rag_eval_qa_full import EVAL_QA

BASE_URL = "http://127.0.0.1:8000"
TOKEN = os.getenv("TEST_JWT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not TOKEN:
    print("ERROR: TEST_JWT_TOKEN environment variable not set.")
    print('  PowerShell: $env:TEST_JWT_TOKEN="your-fresh-token"')
    sys.exit(1)

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

judge_client = Anthropic(api_key=ANTHROPIC_API_KEY)
JUDGE_MODEL = "claude-sonnet-4-5"

GRADER_SYSTEM_PROMPT = """You are grading the output of a support-ticket AI agent
against a known expected answer. You will be given:
- the question that was asked
- the agent's actual answer
- a description of what the expected/correct answer should contain
- grading notes describing what to focus on

Respond with ONLY a raw JSON object, no markdown, no code fences, in this format:
{"verdict": "correct" | "partial" | "incorrect", "reason": "one or two sentence explanation"}

Grading guidance:
- "correct": the actual answer satisfies the expected answer's substance and
  respects the grading notes (does not need to match wording exactly).
- "partial": the actual answer gets the general direction right but misses
  a specific required detail, or is vague where specificity was expected.
- "incorrect": the actual answer contradicts the expected answer, fails a
  stated FAIL condition in the grading notes, or is a hallucination.
- Some questions are explicitly open-ended/exploratory (grading_notes will
  say so, e.g. near-duplicate confidence probes) - for these, grade based
  on whether the agent behaved reasonably and did not do anything the
  grading notes explicitly flag as a FAIL condition, not on matching one
  single 'correct' answer."""


def call_agent(question_text: str) -> str:
    """Send a question to /agent/chat and return the answer text (or an error string)."""
    try:
        resp = requests.post(
            f"{BASE_URL}/agent/chat",
            json={"message": question_text},
            headers=HEADERS,
            timeout=60,
        )
    except requests.exceptions.RequestException as e:
        return f"[REQUEST ERROR: {e}]"

    if resp.status_code != 200:
        return f"[HTTP {resp.status_code}: {resp.text[:300]}]"

    data = resp.json()
    return data.get("answer", "[NO 'answer' FIELD IN RESPONSE]")


def grade_answer(question: dict, actual_answer: str) -> dict:
    """Ask the judge model to grade actual_answer against question's expectations."""
    judge_prompt = f"""Question asked: {question['question']}

Agent's actual answer:
{actual_answer}

Expected answer should contain: {question['expected_answer']}

Grading notes: {question['grading_notes']}"""

    try:
        response = judge_client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=300,
            system=GRADER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        return {"verdict": "error", "reason": f"Judge call failed: {e}"}


def main():
    print(f"Running RAG eval: {len(EVAL_QA)} questions against {BASE_URL}/agent/chat\n")
    results = []

    for i, q in enumerate(EVAL_QA, start=1):
        print(f"[{i}/{len(EVAL_QA)}] {q['id']} ({q['category']})... ", end="", flush=True)

        actual_answer = call_agent(q["question"])
        grade = grade_answer(q, actual_answer)

        result = {
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "actual_answer": actual_answer,
            "expected_answer": q["expected_answer"],
            "verdict": grade.get("verdict", "error"),
            "reason": grade.get("reason", ""),
        }
        results.append(result)
        print(result["verdict"].upper())

        # Small delay to avoid hammering either API back-to-back
        time.sleep(0.5)

    # ---- Summary ----
    total = len(results)
    correct = sum(1 for r in results if r["verdict"] == "correct")
    partial = sum(1 for r in results if r["verdict"] == "partial")
    incorrect = sum(1 for r in results if r["verdict"] == "incorrect")
    errors = sum(1 for r in results if r["verdict"] == "error")

    print(f"\n{'='*60}")
    print(f"RAG EVAL RESULTS: {correct}/{total} correct, {partial} partial, {incorrect} incorrect, {errors} errors")
    print(f"{'='*60}")

    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], {"correct": 0, "partial": 0, "incorrect": 0, "error": 0})
        by_category[r["category"]][r["verdict"]] += 1

    for cat, counts in by_category.items():
        cat_total = sum(counts.values())
        print(f"  {cat}: {counts['correct']}/{cat_total} correct  ({counts['partial']} partial, {counts['incorrect']} incorrect, {counts['error']} error)")

    print("\nFailures and partials worth reviewing:")
    for r in results:
        if r["verdict"] in ("incorrect", "partial", "error"):
            print(f"  [{r['verdict'].upper()}] {r['id']}: {r['question']}")
            print(f"      reason: {r['reason']}")

    with open("rag_eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nFull results written to rag_eval_results.json")


if __name__ == "__main__":
    main()