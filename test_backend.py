import io
import os
import sys
import time
import threading
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

BASE_URL = "http://127.0.0.1:5003"
TEST_IMAGE = os.path.join(PROJECT_ROOT, "test_assets", "test_slide.png")


def section(title):
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print("=" * 65)

def ok(msg): print(f"  [OK]   {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [INFO] {msg}")


def start_server():
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    from app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=5003, use_reloader=False, threaded=True)


def wait_for_server():
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False

def main():
    print("=" * 65)
    print("  Cancer Nuclei Flask Backend - Stage 3 Test")
    print("=" * 65)

    info("Starting Flask server in background thread...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    info("Waiting for server to become ready...")
    if not wait_for_server():
        fail("Server failed to start.")
        sys.exit(1)
    ok("Server is up and accepting requests.")

    results = []

    # 1. Unauthenticated tests
    section("Test 1: Unauthenticated Requests (expect 401)")
    r1 = requests.post(f"{BASE_URL}/predict")
    r2 = requests.get(f"{BASE_URL}/history")
    r3 = requests.get(f"{BASE_URL}/analysis/1")
    passed_unauth = (r1.status_code == 401 and r2.status_code == 401 and r3.status_code == 401)
    results.append(("Unauthenticated endpoints return 401", passed_unauth))
    if passed_unauth: ok("Unauthenticated requests rejected correctly.")
    else: fail(f"Unauthenticated requests not rejected correctly: {r1.status_code}, {r2.status_code}, {r3.status_code}")

    # 2. Login User A
    section("Test 2: Authenticated Workflow (User A)")
    sess_a = requests.Session()
    username_a = f"usera_{int(time.time())}"
    sess_a.post(f"{BASE_URL}/signup", json={"username": username_a, "password": "password123", "confirm_password": "password123"})
    sess_a.post(f"{BASE_URL}/login", json={"username": username_a, "password": "password123"})
    
    # User A Predict
    if not os.path.exists(TEST_IMAGE):
        fail(f"Test image not found at {TEST_IMAGE}. Run stage 1 tests first.")
        sys.exit(1)

    with open(TEST_IMAGE, "rb") as f:
        r_pred = sess_a.post(
            f"{BASE_URL}/predict",
            files={"image": ("test_slide.png", f, "image/png")}
        )
    
    passed_pred = (r_pred.status_code == 200 and r_pred.json().get("success") is True)
    results.append(("Authenticated POST /predict", passed_pred))
    
    analysis_id = None
    if passed_pred:
        analysis_id = r_pred.json().get("analysis_id")
        ok(f"Prediction successful for User A. Analysis ID: {analysis_id}")
    else:
        fail(f"Prediction failed. Status: {r_pred.status_code}, Response: {r_pred.text}")

    # User A History
    r_hist = sess_a.get(f"{BASE_URL}/history")
    passed_hist = (r_hist.status_code == 200 and r_hist.json().get("count") >= 1)
    results.append(("Authenticated GET /history (User A)", passed_hist))
    if passed_hist: ok("User A history retrieved successfully.")
    else: fail("User A history failed.")

    # User A Get Analysis
    if analysis_id:
        r_get = sess_a.get(f"{BASE_URL}/analysis/{analysis_id}")
        passed_get = (r_get.status_code == 200 and r_get.json().get("id") == analysis_id)
        results.append(("Authenticated GET /analysis/<id> (User A)", passed_get))
        if passed_get: ok("User A can access their own analysis.")
        else: fail("User A could not access their own analysis.")

    # 3. Login User B and test isolation
    section("Test 3: Cross-User Isolation (User B)")
    sess_b = requests.Session()
    username_b = f"userb_{int(time.time())}"
    sess_b.post(f"{BASE_URL}/signup", json={"username": username_b, "password": "password123", "confirm_password": "password123"})
    sess_b.post(f"{BASE_URL}/login", json={"username": username_b, "password": "password123"})

    r_hist_b = sess_b.get(f"{BASE_URL}/history")
    passed_hist_b = (r_hist_b.status_code == 200 and r_hist_b.json().get("count") == 0)
    results.append(("User B sees empty history (no leakage)", passed_hist_b))
    if passed_hist_b: ok("User B history is empty.")
    else: fail(f"User B history leaked records! Count: {r_hist_b.json().get('count')}")

    if analysis_id:
        r_get_b = sess_b.get(f"{BASE_URL}/analysis/{analysis_id}")
        passed_get_b = (r_get_b.status_code == 404)
        results.append(("User B cannot access User A's analysis (404)", passed_get_b))
        if passed_get_b: ok("User B gets 404 for User A's analysis.")
        else: fail(f"User B accessed User A's analysis! Status: {r_get_b.status_code}")

    section("SUMMARY")
    total = len(results)
    passed = sum(1 for _, ok_flag in results if ok_flag)
    
    for name, ok_flag in results:
        status = "[PASS]" if ok_flag else "[FAIL]"
        print(f"  {status}  {name}")
        
    print(f"\n  {passed}/{total} tests passed.")
    print("=" * 65)
    
    if passed == total:
        print("  Stage 3 COMPLETE - API Protection is operational.")
    print("=" * 65)
    
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
