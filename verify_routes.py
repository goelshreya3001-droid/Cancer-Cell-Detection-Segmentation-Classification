"""Verify all routes work on a fresh server."""
import threading, time, requests, sys, os

def start_server():
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    from app import create_app
    app = create_app()
    app.run(host='127.0.0.1', port=5005, use_reloader=False)

threading.Thread(target=start_server, daemon=True).start()
time.sleep(15)

BASE = 'http://127.0.0.1:5005'
sess = requests.Session()
ok = 0
total = 0

def check(name, condition, detail=""):
    global ok, total
    total += 1
    if condition:
        ok += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        print(f"  [FAIL] {name}  {detail}")

# 1. POST /signup
r = sess.post(f'{BASE}/signup', json={'username': 'routefix1', 'password': '123', 'confirm_password': '123'})
check("POST /signup", r.status_code == 201, f"status={r.status_code}")

# 2. POST /login
r = sess.post(f'{BASE}/login', json={'username': 'routefix1', 'password': '123'})
check("POST /login", r.status_code == 200, f"status={r.status_code}")

# 3. POST /logout
r = sess.post(f'{BASE}/logout')
check("POST /logout", r.status_code == 200, f"status={r.status_code}")

# 4. Re-login and test POST /predict
sess.post(f'{BASE}/login', json={'username': 'routefix1', 'password': '123'})
with open('test_assets/test_slide.png', 'rb') as f:
    r = sess.post(f'{BASE}/predict', files={'image': ('test.png', f, 'image/png')})
check("POST /predict", r.status_code == 200 and r.json().get('success'), f"status={r.status_code} nuclei={r.json().get('total_nuclei')}")

# 5. GET /history
r = sess.get(f'{BASE}/history')
check("GET /history", r.status_code == 200, f"status={r.status_code} count={r.json().get('count')}")

print(f"\n  {ok}/{total} passed.")
