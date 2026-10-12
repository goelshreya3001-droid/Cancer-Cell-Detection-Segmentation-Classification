"""
Authentication Backend Test Suite (updated).
Tests signup, login, logout, session state,
email validation, duplicate email handling, and theme-related JS behaviour notes.
"""

import threading
import time
import requests
import sys
import os

BASE_URL = "http://127.0.0.1:5001"

def start_server():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    from app import create_app
    app = create_app()
    app.run(host='127.0.0.1', port=5001, use_reloader=False)

def wait_for_server():
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=1)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False

def main():
    print("Starting Flask server...")
    threading.Thread(target=start_server, daemon=True).start()
    if not wait_for_server():
        print("Failed to start server.")
        sys.exit(1)

    print("Server is up. Running auth tests...\n")
    session = requests.Session()
    ts = int(time.time())

    # ── 1. Missing fields ──────────────────────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={"username": "testuser"})
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("PASS: Missing fields handled")

    # ── 2. Password mismatch ───────────────────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": "testuser",
        "email": f"test_{ts}@example.com",
        "password": "123",
        "confirm_password": "456"
    })
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    print("PASS: Password mismatch handled")

    # ── 3. Missing email (email is now mandatory) ──────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": f"usernomail_{ts}",
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 400, f"Expected 400 for missing email, got {r.status_code}"
    print("PASS: Missing email rejected (email is mandatory)")

    # ── 4. Invalid email format ────────────────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": f"userbademail_{ts}",
        "email": "not-an-email",
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 400, f"Expected 400 for invalid email, got {r.status_code}"
    print("PASS: Invalid email format rejected")

    # ── 5. Successful signup ───────────────────────────────────────
    test_username = f"user_{ts}"
    test_email    = f"user_{ts}@example.com"
    r = session.post(f"{BASE_URL}/signup", json={
        "username": test_username,
        "email": test_email,
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 201, f"Signup failed: {r.status_code} — {r.text}"
    print("PASS: Successful signup")

    # ── 6. Duplicate username ──────────────────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": test_username,
        "email": f"different_{ts}@example.com",
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 409, f"Expected 409 for duplicate username, got {r.status_code}"
    print("PASS: Duplicate username rejected")

    # ── 7. Duplicate email (same case) ────────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": f"different_user_{ts}",
        "email": test_email,
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 409, f"Expected 409 for duplicate email, got {r.status_code}"
    print("PASS: Duplicate email rejected")

    # ── 8. Duplicate email (case variation) ────────────────────────
    r = session.post(f"{BASE_URL}/signup", json={
        "username": f"another_user_{ts}",
        "email": test_email.upper(),     # UPPERCASE variant
        "password": "password123",
        "confirm_password": "password123"
    })
    assert r.status_code == 409, f"Expected 409 for case-variant duplicate email, got {r.status_code}"
    print("PASS: Case-variant duplicate email rejected")

    # ── 9. Invalid login ───────────────────────────────────────────
    r = session.post(f"{BASE_URL}/login", json={
        "username": test_username,
        "password": "wrongpassword"
    })
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    print("PASS: Invalid login handled")

    # ── 10. Correct login & session verification ───────────────────
    r = session.post(f"{BASE_URL}/login", json={
        "username": test_username,
        "password": "password123"
    })
    assert r.status_code == 200, f"Login failed: {r.status_code}"
    assert "session" in session.cookies.get_dict(), "Session cookie missing"
    print("PASS: Successful login & session created")

    # ── 11. /me endpoint ──────────────────────────────────────────
    r = session.get(f"{BASE_URL}/me")
    assert r.status_code == 200, f"/me returned {r.status_code}"
    me_data = r.json()
    assert me_data.get("username") == test_username, "Username mismatch in /me"
    assert me_data.get("email") == test_email, f"Email mismatch: {me_data.get('email')} != {test_email}"
    print("PASS: /me returns correct username and normalised email")

    # ── 12. Logout ────────────────────────────────────────────────
    r = session.post(f"{BASE_URL}/logout")
    assert r.status_code == 200, f"Logout failed: {r.status_code}"
    print("PASS: Successful logout")

    # ── 13. /me after logout returns 401 ─────────────────────────
    r = session.get(f"{BASE_URL}/me")
    assert r.status_code == 401, f"Expected 401 after logout, got {r.status_code}"
    print("PASS: /me correctly returns 401 after logout")

    # ── Theme toggle note ─────────────────────────────────────────
    print("\nINFO: Theme toggle is implemented purely in JavaScript + CSS custom properties.")
    print("INFO: No backend endpoint is involved — theme is persisted in localStorage.")
    print("INFO: Manual browser testing of theme toggle required (not automatable here).")

    print("\nAll Auth Tests Passed!")

if __name__ == "__main__":
    main()
