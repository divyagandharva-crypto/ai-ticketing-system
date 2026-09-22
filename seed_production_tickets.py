"""
Seed script for production: creates the same ticket set the local RAG eval
(rag_eval_qa_full.py) expects, so ticket-number references like "ticket 13"
resolve to real data in production too.

WHY THIS EXISTS: the local dev DB has 19 seeded tickets in a specific
order/cluster (see rag_eval_qa_full.py's docstring). Production only ever
had tickets 1 and 2 natively, plus a restricted test ticket (id 3) added
during security verification -- so production's ticket IDs don't line up
with what the eval script expects.

WHAT THIS SCRIPT DOES:
1. Fetches GET /tickets/ from production and prints what's already there.
2. Tells you the next ticket ID that will be assigned.
3. Refuses to proceed automatically if that next ID isn't 4 (since the eval
   script's hardcoded IDs assume ticket 3 already exists as something else
   and the new tickets start filling in from 4 onward) -- instead it prints
   what it WOULD create and asks you to confirm.
4. Once confirmed, creates 16 tickets in the exact order/content local used,
   so they land as close as possible to the ID scheme the eval expects:
     4  = Invoice PDF won't download          (fills the "local ticket 3" slot)
     5  = Something's wrong                    (local ticket 4)
     6  = Can't log into dashboard (dup)        (local ticket 5)
     7  = Login page not working (dup)          (local ticket 6)
     8  = Password reset email never arrives    (local ticket 7)
     9  = Account locked after failed attempts  (local ticket 8)
     10 = Two-factor code not accepted          (local ticket 9)
     11 = Invoice PDF won't download (dup)      (local ticket 10)
     12 = Charged twice for same subscription   (local ticket 11)
     13 = Invoice shows wrong tax amount        (local ticket 12)
     14 = Production API returning 500          (local ticket 13)
     15 = Data appears to be missing after sync (local ticket 14)
     16 = Button color looks slightly off       (local ticket 15)
     17 = Typo in welcome email                 (local ticket 16)
     18 = Something's wrong (dup)               (local ticket 17)
     19 = Please help                           (local ticket 18)
     20 = Cannot sign in to my account          (local ticket 19)

IMPORTANT: because production's ticket 3 is NOT "Invoice PDF won't
download" like local, every ID from here on is shifted +1 versus what
rag_eval_qa_full.py hardcodes. After running this, you MUST update
rag_eval_qa_full.py's ticket_id references (add 1 to every hardcoded
ticket number from 3 onward) -- this script prints the exact mapping at
the end so you can do that update precisely.

Usage:
    $env:TEST_JWT_TOKEN="your-fresh-production-token"
    python seed_production_tickets.py
"""

import os
import sys
import time
import requests

BASE_URL = "https://ai-ticketing-system-omfc.onrender.com"
TOKEN = os.getenv("TEST_JWT_TOKEN")

if not TOKEN:
    print("ERROR: TEST_JWT_TOKEN environment variable not set.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# Same content, same order, as local's seed_test_tickets.py plus the
# earlier "Something's wrong" ticket that predated that script locally.
TICKETS_TO_SEED = [
    {"title": "Invoice PDF won't download", "description": "Export button on invoice page does nothing"},
    {"title": "Something's wrong", "description": "It doesn't work right"},
    {"title": "Can't log into dashboard", "description": "User unable to sign in from Chrome"},
    {"title": "Login page not working", "description": "User reports sign in screen is broken"},
    {"title": "Password reset email never arrives", "description": "Requested password reset three times, no email received"},
    {"title": "Account locked after failed attempts", "description": "User locked out after multiple incorrect password tries"},
    {"title": "Two-factor code not accepted", "description": "SMS code entered correctly but login still rejected"},
    {"title": "Invoice PDF won't download", "description": "Export button on invoice page does nothing"},
    {"title": "Charged twice for same subscription", "description": "Credit card statement shows duplicate charge this month"},
    {"title": "Invoice shows wrong tax amount", "description": "Tax line on latest invoice looks incorrect compared to last month"},
    {"title": "Production API returning 500 for all users", "description": "Entire customer base unable to use the platform since 9am"},
    {"title": "Data appears to be missing after sync", "description": "Customer reports their uploaded records vanished after last sync run"},
    {"title": "Button color looks slightly off on settings page", "description": "Minor visual inconsistency, does not affect functionality"},
    {"title": "Typo in welcome email", "description": "Welcome email says 'Wecome' instead of 'Welcome'"},
    {"title": "Something's wrong", "description": "It doesn't work right"},
    {"title": "Please help", "description": "Not sure what happened but it's broken"},
    {"title": "Cannot sign in to my account", "description": "Getting an error every time I try to log in"},
]


def main():
    resp = requests.get(f"{BASE_URL}/tickets/?limit=100", headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"Could not fetch existing tickets: HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)

    existing = resp.json()
    existing_ids = sorted(t["id"] for t in existing)
    next_id = (max(existing_ids) + 1) if existing_ids else 1

    print(f"Existing production tickets: {existing_ids}")
    print(f"Next ticket ID will be: {next_id}\n")

    if next_id != 4:
        print(f"WARNING: expected the next ID to be 4 (tickets 1, 2, 3 already exist),")
        print(f"but it's actually {next_id}. The ID mapping in this script's docstring")
        print(f"won't be accurate -- proceed only if you understand the shift.\n")

    print(f"About to create {len(TICKETS_TO_SEED)} tickets, starting at id {next_id}:")
    for i, t in enumerate(TICKETS_TO_SEED):
        print(f"  {next_id + i}: {t['title']!r}")

    confirm = input("\nProceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted, nothing created.")
        return

    created = []
    for t in TICKETS_TO_SEED:
        resp = requests.post(f"{BASE_URL}/tickets/", json=t, headers=HEADERS, timeout=30)
        if resp.status_code in (200, 201):
            data = resp.json()
            print(f"Created ticket {data['id']}: {t['title']!r}")
            created.append((data["id"], t["title"]))
        else:
            print(f"FAILED to create {t['title']!r}: HTTP {resp.status_code}: {resp.text}")
        time.sleep(1.0)  # avoid hammering the free-tier instance

    print(f"\nDone. Created {len(created)} tickets.")
    print("\nID mapping (production id -> local id it replaces):")
    for idx, (pid, title) in enumerate(created):
        local_id = idx + 3  # local ticket 3 onward
        print(f"  production {pid} = local {local_id} ({title!r})")


if __name__ == "__main__":
    main()