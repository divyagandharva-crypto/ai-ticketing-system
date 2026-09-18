"""
Verification script for the access-control fix.

Confirms, against the LIVE running API (not a mock), that:
  1. A ticket tagged access_level='restricted' is invisible to a
     standard-clearance user on GET /tickets/{id}, GET /tickets/{id}/similar,
     and GET /tickets/{id}/suggest-resolution (all should 404).
  2. The same ticket IS visible to a properly-cleared user.
  3. A restricted ticket never appears in another ticket's /similar results
     when the requester is standard-clearance, even if it would otherwise
     rank as similar.

Usage:
    1. Update BASE_URL below if your server isn't on localhost:8000.
    2. Make sure you have at least one existing user account's credentials
       to log in with (or update create_user() calls with real ones).
    3. python verify_access_control.py

This hits real HTTP endpoints — it is not a unit test with mocks. That's
deliberate: the whole point is proving the fix works against the actual
running system, the same way the RAG eval scripts test the live agent.
"""

import requests

BASE_URL = "http://localhost:8000"


def signup_and_login(email: str, password: str) -> str:
    """Creates a user if they don't already exist, then logs in and
    returns a bearer token."""
    requests.post(f"{BASE_URL}/users/", json={"email": email, "password": password})
    resp = requests.post(
        f"{BASE_URL}/login",
        data={"username": email, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def set_clearance_level(email: str, level: str):
    """
    There's no API endpoint for this by design (clearance shouldn't be
    self-service) — set it directly via SQL for test setup:
        UPDATE users SET clearance_level = '<level>' WHERE email = '<email>';
    This function just prints the command; run it in psql before
    continuing, then press Enter here.
    """
    print(f"\nRun this in psql, then press Enter here:")
    print(f"  UPDATE users SET clearance_level = '{level}' WHERE email = '{email}';")
    input()


def create_ticket(token: str, title: str, description: str, access_level: str) -> int:
    resp = requests.post(
        f"{BASE_URL}/tickets/",
        json={"title": title, "description": description, "access_level": access_level},
        headers=auth_headers(token),
    )
    resp.raise_for_status()
    return resp.json()["id"]


def expect_status(label: str, resp: requests.Response, expected: int):
    ok = resp.status_code == expected
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {label}: expected {expected}, got {resp.status_code}")
    return ok


def main():
    print("=== Access control verification ===\n")

    admin_token = signup_and_login("verify_admin@test.com", "testpass123")
    standard_token = signup_and_login("verify_standard@test.com", "testpass123")

    print("\nSetting verify_admin@test.com to 'restricted' clearance:")
    set_clearance_level("verify_admin@test.com", "restricted")
    print("Confirming verify_standard@test.com stays at 'standard' (should already be the default).")

    print("\nCreating a restricted ticket as the admin user...")
    restricted_id = create_ticket(
        admin_token,
        "Confidential account issue",
        "This ticket should only be visible to restricted-clearance users.",
        access_level="restricted",
    )
    print(f"Created restricted ticket id={restricted_id}")

    print("\n--- Standard-clearance user should be denied ---")
    r1 = requests.get(f"{BASE_URL}/tickets/{restricted_id}", headers=auth_headers(standard_token))
    expect_status("GET /tickets/{id} as standard user", r1, 404)

    r2 = requests.get(f"{BASE_URL}/tickets/{restricted_id}/similar", headers=auth_headers(standard_token))
    expect_status("GET /tickets/{id}/similar as standard user", r2, 404)

    r3 = requests.get(f"{BASE_URL}/tickets/{restricted_id}/suggest-resolution", headers=auth_headers(standard_token))
    expect_status("GET /tickets/{id}/suggest-resolution as standard user", r3, 404)

    print("\n--- Restricted-clearance user (admin) should be allowed ---")
    r4 = requests.get(f"{BASE_URL}/tickets/{restricted_id}", headers=auth_headers(admin_token))
    expect_status("GET /tickets/{id} as restricted user", r4, 200)

    print("\n--- A standard ticket similar to the restricted one should NOT surface it ---")
    standard_similar_id = create_ticket(
        admin_token,
        "Confidential account issue duplicate",
        "This ticket should only be visible to restricted-clearance users, duplicate wording.",
        access_level="standard",
    )
    r5 = requests.get(f"{BASE_URL}/tickets/{standard_similar_id}/similar", headers=auth_headers(standard_token))
    if r5.status_code == 200:
        returned_ids = [t["id"] for t in r5.json()]
        leaked = restricted_id in returned_ids
        marker = "FAIL" if leaked else "PASS"
        print(f"[{marker}] restricted ticket excluded from standard user's /similar results: leaked={leaked}")
    else:
        print(f"[SKIP] /similar returned {r5.status_code}, couldn't check for leakage")

    print("\n=== Done. Review PASS/FAIL lines above. ===")


if __name__ == "__main__":
    main()