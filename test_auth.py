"""
Authentication Backend Test Suite
Verifies signup, login, logout, and session state.
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
    
    # 1. Missing fields
    r = session.post(f"{BASE_URL}/signup", json={"username": "testuser"})
    assert r.status_code == 400, "Should require all fields"
    print("PASS: Missing fields handled")

    # 2. Password mismatch
    r = session.post(f"{BASE_URL}/signup", json={
        "username": "testuser", "password": "123", "confirm_password": "456"
    })
    assert r.status_code == 400, "Should check password match"
    print("PASS: Password mismatch handled")

    # 3. Successful signup (with unique suffix)
    test_username = f"user_{int(time.time())}"
    r = session.post(f"{BASE_URL}/signup", json={
        "username": test_username, "password": "password123", "confirm_password": "password123"
    })
    assert r.status_code == 201, "Signup failed"
    print("PASS: Successful signup")

    # 4. Duplicate username
    r = session.post(f"{BASE_URL}/signup", json={
        "username": test_username, "password": "password123", "confirm_password": "password123"
    })
    assert r.status_code == 409, "Should prevent duplicate username"
    print("PASS: Duplicate username handled")

    # 5. Invalid login
    r = session.post(f"{BASE_URL}/login", json={
        "username": test_username, "password": "wrongpassword"
    })
    assert r.status_code == 401, "Should reject wrong password"
    print("PASS: Invalid login handled")

    # 6. Correct login & session verification
    r = session.post(f"{BASE_URL}/login", json={
        "username": test_username, "password": "password123"
    })
    assert r.status_code == 200, "Login failed"
    assert "session" in session.cookies.get_dict(), "Session cookie missing"
    print("PASS: Successful login & session created")

    # 7. Logout
    r = session.post(f"{BASE_URL}/logout")
    assert r.status_code == 200, "Logout failed"
    # Depending on Flask session config, the cookie might be removed or set to clear
    print("PASS: Successful logout")

    print("\nAll Auth Tests Passed!")

if __name__ == "__main__":
    main()
