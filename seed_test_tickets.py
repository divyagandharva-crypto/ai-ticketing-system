"""
Seed script: creates a spread of test tickets for eval harness testing.
Run this against your running FastAPI app (adjust BASE_URL/TOKEN as needed).

Categories covered:
- Login/auth issues (clear)
- Billing/invoice issues (clear)
- Clearly urgent/critical issues
- Clearly low-urgency/cosmetic issues
- Deliberately vague issues (for low-confidence testing)
- Near-duplicate phrasing of same issue (for retrieval/dedup testing)
"""

import requests

BASE_URL = "http://127.0.0.1:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJleHAiOjE3ODk1OTQxOTd9.PgBje0jQ23QvHLWoix6xWbUCZD_R2IxWTXcTi2FDo_A"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

TEST_TICKETS = [
    # --- Login / auth cluster ---
    {"title": "Can't log into dashboard", "description": "User unable to sign in from Chrome"},
    {"title": "Login page not working", "description": "User reports sign in screen is broken"},
    {"title": "Password reset email never arrives", "description": "Requested password reset three times, no email received"},
    {"title": "Account locked after failed attempts", "description": "User locked out after multiple incorrect password tries"},
    {"title": "Two-factor code not accepted", "description": "SMS code entered correctly but login still rejected"},

    # --- Billing / invoice cluster ---
    {"title": "Invoice PDF won't download", "description": "Export button on invoice page does nothing"},
    {"title": "Charged twice for same subscription", "description": "Credit card statement shows duplicate charge this month"},
    {"title": "Invoice shows wrong tax amount", "description": "Tax line on latest invoice looks incorrect compared to last month"},

    # --- Clearly urgent / critical ---
    {"title": "Production API returning 500 for all users", "description": "Entire customer base unable to use the platform since 9am"},
    {"title": "Data appears to be missing after sync", "description": "Customer reports their uploaded records vanished after last sync run"},

    # --- Clearly low urgency / cosmetic ---
    {"title": "Button color looks slightly off on settings page", "description": "Minor visual inconsistency, does not affect functionality"},
    {"title": "Typo in welcome email", "description": "Welcome email says 'Wecome' instead of 'Welcome'"},

    # --- Deliberately vague (low-confidence testing) ---
    {"title": "Something's wrong", "description": "It doesn't work right"},
    {"title": "Please help", "description": "Not sure what happened but it's broken"},

    # --- Near-duplicate phrasing (retrieval/dedup testing) ---
    {"title": "Cannot sign in to my account", "description": "Getting an error every time I try to log in"},
]

def seed():
    created = []
    for t in TEST_TICKETS:
        resp = requests.post(f"{BASE_URL}/tickets/", json=t, headers=HEADERS)
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"Created ticket {data.get('id')}: {t['title']}")
            created.append(data.get("id"))
        else:
            print(f"FAILED to create '{t['title']}': {resp.status_code} {resp.text}")
    print(f"\nDone. Created {len(created)} tickets: {created}")
    print("\nReminder: if you have a backfill_embeddings.py script, run it now")
    print("so these new tickets get embeddings for similarity search.")

if __name__ == "__main__":
    seed()