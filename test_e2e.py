"""
Stage 4 Final End-to-End Test

This script verifies the full application flow including UI, static files,
and API endpoints using a locally running Flask server thread.
"""

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

BASE_URL = "http://127.0.0.1:5000"
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
    app.run(host="127.0.0.1", port=5000, use_reloader=False, threaded=True)

def wait_for_server():
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200: return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    return False


def test_ui_root():
    section("Test 1: GET / (Dashboard UI)")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        if r.status_code == 200 and "<html" in r.text.lower():
            ok("GET / returned 200 OK with HTML content.")
            return True
        else:
            fail(f"Unexpected response. Status: {r.status_code}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_static_files():
    section("Test 2: Static Files (CSS & JS)")
    passed = True
    try:
        r_css = requests.get(f"{BASE_URL}/static/css/style.css", timeout=5)
        if r_css.status_code == 200 and ("background" in r_css.text or "--brand-primary" in r_css.text):
            ok("CSS loaded successfully.")
        else:
            fail(f"CSS failed. Status: {r_css.status_code}")
            passed = False

        r_js = requests.get(f"{BASE_URL}/static/js/main.js", timeout=5)
        if r_js.status_code == 200 and "DOMContentLoaded" in r_js.text:
            ok("JS loaded successfully.")
        else:
            fail(f"JS failed. Status: {r_js.status_code}")
            passed = False
            
        return passed
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_predict_flow(analysis_id_holder, session):
    section("Test 3: POST /predict (Full ML Inference Flow)")
    if not os.path.exists(TEST_IMAGE):
        fail("Test image missing.")
        return False
        
    try:
        with open(TEST_IMAGE, "rb") as f:
            r = session.post(
                f"{BASE_URL}/predict",
                files={"image": ("test_slide.png", f, "image/png")},
                timeout=120
            )
        
        data = r.json()
        if r.status_code == 200 and data.get("success"):
            ok("Inference completed successfully.")
            
            # Verify required fields
            fields = ["total_nuclei", "malignant_nuclei", "inflammatory_nuclei", 
                      "healthy_nuclei", "stromal_nuclei", "other_nuclei", 
                      "processing_time_sec", "overlay_url", "mask_url", "upload_url"]
            
            missing = [f for f in fields if f not in data]
            if missing:
                fail(f"Missing fields in response: {missing}")
                return False
                
            ok("All required metrics and image URLs are present in response.")
            
            print("\n  --- Inference Results ---")
            for field in fields:
                print(f"  {field.ljust(20)}: {data.get(field)}")
                
            analysis_id_holder.append(data.get("analysis_id"))
            return True
        else:
            fail(f"Predict failed: {r.status_code} - {data}")
            return False
            
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_history(session):
    section("Test 4: GET /history")
    try:
        r = session.get(f"{BASE_URL}/history", timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("success"):
            ok(f"History returned successfully. Count: {data.get('count')}")
            return True
        else:
            fail(f"History failed: {r.status_code}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_get_analysis(analysis_id, session):
    section(f"Test 5: GET /analysis/{analysis_id}")
    try:
        r = session.get(f"{BASE_URL}/analysis/{analysis_id}", timeout=10)
        data = r.json()
        if r.status_code == 200 and data.get("success"):
            ok("Analysis fetched successfully.")
            info(f"Total Nuclei: {data.get('total_nuclei')}")
            return True
        else:
            fail(f"Failed to fetch analysis: {r.status_code}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def test_invalid_file(session):
    section("Test 6: POST /predict (Invalid File)")
    try:
        fake_file = io.BytesIO(b"this is not an image")
        r = session.post(
            f"{BASE_URL}/predict",
            files={"image": ("test.txt", fake_file, "text/plain")},
            timeout=10
        )
        if r.status_code == 400 and r.json().get("success") is False:
            ok("Invalid file properly rejected (400 Bad Request).")
            return True
        else:
            fail(f"Expected 400, got {r.status_code}")
            return False
    except Exception as e:
        fail(f"Request failed: {e}")
        return False


def main():
    print("=" * 65)
    print("  Cancer Nuclei - Stage 4 E2E Test")
    print("=" * 65)

    info("Starting Flask server...")
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    info("Waiting for server to become ready...")
    if not wait_for_server():
        fail("Server failed to start.")
        sys.exit(1)
    ok("Server is running.")

    session = requests.Session()
    ts = int(time.time())
    user = f"e2e_user_{ts}"

    # ── Signup ─────────────────────────────────────────────────────────────
    try:
        r_signup = session.post(f"{BASE_URL}/signup", json={
            "username": user,
            "email": f"{user}@example.com",
            "password": "password123",
            "confirm_password": "password123",
        }, timeout=10)
    except Exception as exc:
        fail(f"POST /signup connection failed: {exc}")
        sys.exit(1)

    try:
        data_signup = r_signup.json()
    except Exception:
        fail(f"POST /signup returned non-JSON response (HTTP {r_signup.status_code}): {r_signup.text[:200]}")
        sys.exit(1)

    if r_signup.status_code != 201 or not data_signup.get("success"):
        fail(f"POST /signup failed (HTTP {r_signup.status_code}): {data_signup}")
        sys.exit(1)
    ok(f"User signup succeeded: {user}")

    # ── Login ──────────────────────────────────────────────────────────────
    try:
        r_login = session.post(f"{BASE_URL}/login", json={
            "username": user,
            "password": "password123",
        }, timeout=10)
    except Exception as exc:
        fail(f"POST /login connection failed: {exc}")
        sys.exit(1)

    try:
        data_login = r_login.json()
    except Exception:
        fail(f"POST /login returned non-JSON response (HTTP {r_login.status_code}): {r_login.text[:200]}")
        sys.exit(1)

    if r_login.status_code != 200 or not data_login.get("success"):
        fail(f"POST /login failed (HTTP {r_login.status_code}): {data_login}")
        sys.exit(1)
    ok("User login succeeded; authenticated session established.")

    results = []
    analysis_id_holder = []

    results.append(("UI Dashboard (GET /)", test_ui_root()))
    results.append(("Static Files Loading", test_static_files()))
    results.append(("ML Inference Flow", test_predict_flow(analysis_id_holder, session)))
    results.append(("Analysis History", test_history(session)))
    
    if analysis_id_holder:
        results.append(("Fetch Single Analysis", test_get_analysis(analysis_id_holder[0], session)))
    
    results.append(("Invalid File Handling", test_invalid_file(session)))

    section("FINAL SUMMARY")
    passed = sum(1 for _, ok_flag in results if ok_flag)
    total = len(results)
    
    for name, ok_flag in results:
        status = "[PASS]" if ok_flag else "[FAIL]"
        print(f"  {status}  {name}")
        
    print(f"\n  {passed}/{total} tests passed.")
    print("=" * 65)
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
