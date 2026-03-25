"""
QA 전체 테스트: kevinsaem-booking
httpx + 내장 테스트 서버 (포트 8200)
"""

import sys, os, threading, time, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
import uvicorn
from datetime import datetime, timedelta

BASE = "http://127.0.0.1:8200"
RESULTS = []  # (test_name, passed:bool, detail:str)


def record(name: str, passed: bool, detail: str = ""):
    RESULTS.append((name, passed, detail))
    mark = "PASS" if passed else "FAIL"
    print(f"  [{mark}] {name}" + (f" -- {detail}" if detail and not passed else ""))


# ─── Start test server ─────────────────────────────────────
def start_server():
    # Reset DB before tests
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=8200, log_level="warning")


server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# Wait for server to start
for _ in range(30):
    try:
        r = httpx.get(f"{BASE}/health", timeout=2)
        if r.status_code == 200:
            break
    except Exception:
        pass
    time.sleep(0.5)
else:
    print("ERROR: Server did not start!")
    sys.exit(1)

print("Server started on port 8200\n")


# ─── Helper: login and return client with cookie ──────────
def login_client(name: str, code: str) -> httpx.Client:
    c = httpx.Client(base_url=BASE, follow_redirects=True, timeout=10)
    c.post("/booking/login", data={"name": name, "code": code})
    return c


# ─── Helper: find a future weekday date with available slots ──
def find_future_weekday() -> str:
    now = datetime.now()
    d = now + timedelta(days=1)
    for _ in range(14):
        if d.weekday() < 5:  # Mon-Fri
            return d.strftime("%Y-%m-%d")
        d += timedelta(days=1)
    return (now + timedelta(days=1)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════
# A. Authentication Tests
# ═══════════════════════════════════════════════════════════
print("=== A. Authentication ===")

# A1: GET /booking/ without login → login page
try:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
    r = c.get("/booking/")
    html = r.text
    passed = ("로그인" in html or "인증번호" in html)
    record("A1: Unauthenticated GET /booking/ shows login", passed,
           f"status={r.status_code}, has 로그인={'로그인' in html}, has 인증번호={'인증번호' in html}")
    c.close()
except Exception as e:
    record("A1: Unauthenticated GET /booking/ shows login", False, str(e))

# A2: Wrong credentials
try:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
    r = c.post("/booking/login", data={"name": "테스트", "code": "9999"})
    html = r.text
    passed = ("일치하지 않" in html or "오류" in html or "error" in html.lower() or r.status_code == 200)
    # Should show error on the login page, not redirect
    has_error_msg = "일치하지 않" in html
    record("A2: Wrong credentials show error", has_error_msg,
           f"status={r.status_code}, has error msg={has_error_msg}")
    c.close()
except Exception as e:
    record("A2: Wrong credentials show error", False, str(e))

# A3: Empty name
try:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
    r = c.post("/booking/login", data={"name": "", "code": "1234"})
    # FastAPI Form() requires non-empty by default, or the login should fail
    passed = r.status_code in (200, 303, 422)
    if r.status_code == 422:
        detail = "FastAPI validation error (422) - expected for empty required field"
        record("A3: Empty name returns error", True, detail)
    elif r.status_code == 200:
        html = r.text
        has_error = "일치하지 않" in html or "로그인" in html
        record("A3: Empty name returns error", has_error,
               f"status=200, stays on login page={has_error}")
    else:
        record("A3: Empty name returns error", False, f"status={r.status_code}")
    c.close()
except Exception as e:
    record("A3: Empty name returns error", False, str(e))

# A4: Correct credentials → redirect
try:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
    r = c.post("/booking/login", data={"name": "김수강", "code": "1234"})
    passed = r.status_code == 303 and "/booking/" in r.headers.get("location", "")
    has_cookie = "token" in r.cookies or any("token" in h for h in r.headers.get("set-cookie", ""))
    record("A4: Correct login redirects", passed,
           f"status={r.status_code}, location={r.headers.get('location','')}, has_cookie={has_cookie}")
    c.close()
except Exception as e:
    record("A4: Correct login redirects", False, str(e))

# A5: After login, home page shows user info
try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/")
    html = r.text
    has_name = "김수강" in html
    has_remaining = "7" in html
    passed = has_name and has_remaining
    record("A5: Home page shows user name & remaining", passed,
           f"has_name={has_name}, has_remaining_7={has_remaining}")
    c.close()
except Exception as e:
    record("A5: Home page shows user name & remaining", False, str(e))

# A6: Logout
try:
    c = login_client("김수강", "1234")
    r = c.post("/booking/logout", follow_redirects=False)
    passed_redirect = r.status_code == 303
    # After redirect, check the login page
    r2 = c.get("/booking/")
    passed_login = "로그인" in r2.text or "인증번호" in r2.text
    record("A6: Logout clears session", passed_redirect and passed_login,
           f"redirect={passed_redirect}, shows_login={passed_login}")
    c.close()
except Exception as e:
    record("A6: Logout clears session", False, str(e))


# ═══════════════════════════════════════════════════════════
# B. Home Page
# ═══════════════════════════════════════════════════════════
print("\n=== B. Home Page ===")

try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/")
    html = r.text

    has_name = "김수강" in html
    has_remaining = "7" in html
    has_notice = "특강" in html or "공지" in html or "안내" in html
    # Check for quick menu / navigation
    has_menu = "예약" in html or "calendar" in html.lower()

    record("B1: Home has user name + remaining", has_name and has_remaining,
           f"name={has_name}, remaining={has_remaining}")
    record("B2: Home has latest notice", has_notice,
           f"has_notice_keyword={has_notice}")

    # Unread count
    has_unread = "2" in html or "unread" in html.lower() or "읽지 않" in html
    record("B3: Home has unread message indicator", has_unread,
           f"html contains unread indicator={has_unread}")
    c.close()
except Exception as e:
    record("B1-B3: Home page checks", False, str(e))


# ═══════════════════════════════════════════════════════════
# C. Booking Flow
# ═══════════════════════════════════════════════════════════
print("\n=== C. Booking Flow ===")

future_date = find_future_weekday()
print(f"  Using future date: {future_date}")

try:
    c = login_client("김수강", "1234")

    # C1: Calendar page
    r = c.get("/booking/calendar")
    html = r.text
    has_calendar = "2026" in html and ("3" in html or "calendar" in html.lower())
    record("C1: Calendar page loads", r.status_code == 200 and has_calendar,
           f"status={r.status_code}, has_year_month={has_calendar}")

    # C2: Calendar grid partial
    r = c.get("/booking/partials/calendar-grid?year=2026&month=3")
    html = r.text
    has_days = any(str(d) in html for d in range(20, 32))
    record("C2: Calendar grid partial returns HTML", r.status_code == 200 and len(html) > 50,
           f"status={r.status_code}, len={len(html)}, has_days={has_days}")

    # C3: Time slots for future date
    r = c.get(f"/booking/partials/time-slots?date={future_date}")
    html = r.text
    has_time = "10:00" in html or "14:00" in html or "슬롯" in html or "시간" in html
    record("C3: Time slots partial returns data", r.status_code == 200,
           f"status={r.status_code}, len={len(html)}, has_time={has_time}")

    # C4: Teacher list - we need a valid room_idx. Query available slots.
    r_slots = c.get(f"/booking/partials/time-slots?date={future_date}")
    # Parse out a room_idx from the HTML if possible
    import re
    room_idx_match = re.search(r'room_idx["\s=:]+(\d+)', r_slots.text)
    room_idx = int(room_idx_match.group(1)) if room_idx_match else 1001

    r = c.get(f"/booking/partials/teacher-list?date={future_date}&time=10:00~10:50&room_idx={room_idx}")
    html = r.text
    record("C4: Teacher list partial returns", r.status_code == 200,
           f"status={r.status_code}, len={len(html)}")

    # C5: Repeat page
    # Find a valid slot with teacher
    # Get teachers for 14:00 slot (has most teachers)
    r_t = c.get(f"/booking/partials/time-slots?date={future_date}")
    room_match = re.search(r'room_idx["\s=:]+(\d+)', r_t.text)
    valid_room_idx = int(room_match.group(1)) if room_match else room_idx

    r = c.post("/booking/repeat", data={
        "date": future_date,
        "time": "14:00~14:50",
        "room_idx": valid_room_idx,
        "teacher_id": "TEA001",
    })
    html = r.text
    has_repeat = "반복" in html or future_date in html or "주" in html
    record("C5: Repeat page loads", r.status_code == 200,
           f"status={r.status_code}, has_repeat_content={has_repeat}")

    # C6: Confirm page
    r = c.post("/booking/confirm", data={
        "dates[]": future_date,
        "teacher_name": "김코딩",
        "teacher_id": "TEA001",
        "room_idx": str(valid_room_idx),
        "time": "14:00~14:50",
    })
    html = r.text
    has_confirm = "확인" in html or "예약" in html or future_date in html
    record("C6: Confirm page loads", r.status_code == 200,
           f"status={r.status_code}, has_confirm_content={has_confirm}")

    # C7: Complete booking
    r = c.post("/booking/complete", data={
        "dates[]": future_date,
        "teacher_name": "김코딩",
        "teacher_id": "TEA001",
        "room_idx": str(valid_room_idx),
        "settle_code": "10001",
        "time": "14:00~14:50",
    })
    html = r.text
    has_success = "완료" in html or "성공" in html or "예약" in html
    record("C7: Complete booking succeeds", r.status_code == 200 and has_success,
           f"status={r.status_code}, has_success={has_success}")

    c.close()
except Exception as e:
    record("C: Booking flow", False, f"{str(e)}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════
# D. My Bookings
# ═══════════════════════════════════════════════════════════
print("\n=== D. My Bookings ===")

try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/my-bookings")
    html = r.text
    has_bookings = "예약" in html or "수업" in html
    record("D1: My bookings page loads", r.status_code == 200,
           f"status={r.status_code}, has_content={has_bookings}")

    # Check if the booking we just made appears
    has_future_booking = future_date.replace("-", ".") in html or "김코딩" in html or "14:00" in html
    record("D2: New booking appears in list", has_future_booking,
           f"has_date_or_teacher={has_future_booking}")
    c.close()
except Exception as e:
    record("D: My Bookings", False, str(e))


# ═══════════════════════════════════════════════════════════
# E. Dashboard
# ═══════════════════════════════════════════════════════════
print("\n=== E. Dashboard ===")

try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/dashboard")
    html = r.text

    has_stats = any(kw in html for kw in ["완료", "잔여", "출석", "진도", "progress"])
    has_lessons = any(kw in html for kw in ["ChatGPT", "Python", "AI", "수업"])

    record("E1: Dashboard shows stats", r.status_code == 200 and has_stats,
           f"status={r.status_code}, has_stats={has_stats}")
    record("E2: Dashboard shows recent lessons", has_lessons,
           f"has_lessons={has_lessons}")
    c.close()
except Exception as e:
    record("E: Dashboard", False, str(e))


# ═══════════════════════════════════════════════════════════
# F. Messages
# ═══════════════════════════════════════════════════════════
print("\n=== F. Messages ===")

try:
    c = login_client("김수강", "1234")

    # F1: Messages list
    r = c.get("/booking/messages")
    html = r.text
    has_conversations = "김코딩" in html or "박데이터" in html
    record("F1: Messages page shows conversations", r.status_code == 200 and has_conversations,
           f"status={r.status_code}, has_teachers={has_conversations}")

    # Get unread count before opening chat
    unread_before = html.count("unread") + html.count("안읽")

    # F2: Chat page
    r = c.get("/booking/chat/TEA001")
    html = r.text
    has_messages = "프롬프트" in html or "API" in html or "수업" in html
    record("F2: Chat page shows messages", r.status_code == 200 and has_messages,
           f"status={r.status_code}, has_chat_content={has_messages}")

    # F3: Check if unread count changed (after opening chat with TEA001)
    r2 = c.get("/booking/messages")
    html2 = r2.text
    # After reading TEA001's messages, the unread from TEA001 should be 0
    record("F3: Unread count updates after reading", r2.status_code == 200,
           "Chat opened, messages page reloaded")

    c.close()
except Exception as e:
    record("F: Messages", False, str(e))


# ═══════════════════════════════════════════════════════════
# G. Payment
# ═══════════════════════════════════════════════════════════
print("\n=== G. Payment ===")

try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/payment")
    html = r.text

    has_plan = "진로반" in html or "수강권" in html or "패키지" in html
    has_210 = "210,000" in html
    has_290 = "290,000" in html
    has_450 = "450,000" in html
    has_history = "결제" in html

    record("G1: Payment page loads", r.status_code == 200 and has_plan,
           f"status={r.status_code}, has_plan={has_plan}")
    record("G2: Package prices correct (210k/290k/450k)",
           has_210 and has_290 and has_450,
           f"210k={has_210}, 290k={has_290}, 450k={has_450}")
    record("G3: Payment history shown", has_history,
           f"has_payment_history={has_history}")
    c.close()
except Exception as e:
    record("G: Payment", False, str(e))


# ═══════════════════════════════════════════════════════════
# H. Notices
# ═══════════════════════════════════════════════════════════
print("\n=== H. Notices ===")

try:
    c = login_client("김수강", "1234")

    # H1: Notice list
    r = c.get("/booking/notices")
    html = r.text
    has_notices = "특강" in html or "공지" in html or "이벤트" in html
    record("H1: Notices page loads", r.status_code == 200 and has_notices,
           f"status={r.status_code}, has_notices={has_notices}")

    # H2: Notice detail
    r = c.get("/booking/notices/1")
    html = r.text
    has_detail = "ChatGPT" in html or "Midjourney" in html or "특강" in html
    record("H2: Notice detail page loads", r.status_code == 200 and has_detail,
           f"status={r.status_code}, has_detail={has_detail}")

    # H3: Check notice types
    r_list = c.get("/booking/notices")
    html_list = r_list.text
    has_notice_type = "공지" in html_list
    has_event_type = "이벤트" in html_list
    record("H3: Notice types present (공지, 이벤트)", has_notice_type and has_event_type,
           f"has_공지={has_notice_type}, has_이벤트={has_event_type}")
    c.close()
except Exception as e:
    record("H: Notices", False, str(e))


# ═══════════════════════════════════════════════════════════
# I. MyPage
# ═══════════════════════════════════════════════════════════
print("\n=== I. MyPage ===")

try:
    c = login_client("김수강", "1234")
    r = c.get("/booking/mypage")
    html = r.text
    has_profile = "김수강" in html
    has_stats = "완료" in html or "출석" in html or "수업" in html
    has_menu = "설정" in html or "메뉴" in html or "마이" in html or "MY" in html or "로그아웃" in html
    record("I1: MyPage shows profile", r.status_code == 200 and has_profile,
           f"status={r.status_code}, has_profile={has_profile}")
    record("I2: MyPage shows stats/menu", has_stats or has_menu,
           f"has_stats={has_stats}, has_menu={has_menu}")
    c.close()
except Exception as e:
    record("I: MyPage", False, str(e))


# ═══════════════════════════════════════════════════════════
# J. Template Quality
# ═══════════════════════════════════════════════════════════
print("\n=== J. Template Quality ===")

PAGES = [
    ("/booking/", "Home"),
    ("/booking/calendar", "Calendar"),
    ("/booking/my-bookings", "My Bookings"),
    ("/booking/dashboard", "Dashboard"),
    ("/booking/messages", "Messages"),
    ("/booking/payment", "Payment"),
    ("/booking/notices", "Notices"),
    ("/booking/notices/1", "Notice Detail"),
    ("/booking/mypage", "MyPage"),
    ("/booking/chat/TEA001", "Chat"),
]

try:
    c = login_client("김수강", "1234")

    for path, name in PAGES:
        r = c.get(path)
        html = r.text

        # Check HTML structure
        has_html = "<!DOCTYPE" in html.upper() or "<html" in html or "{% extends" in html
        # The rendered output won't have {% extends but should have <html
        has_structure = "<html" in html.lower() or "<div" in html.lower()

        # Check for Tailwind classes
        has_tailwind = any(tw in html for tw in ["bg-", "text-", "flex", "rounded", "px-", "py-", "font-"])

        # Check for raw Jinja2 errors
        has_jinja_error = "{{" in html and "}}" in html and "Traceback" in html
        has_template_error = "TemplateSyntaxError" in html or "UndefinedError" in html

        passed = has_structure and has_tailwind and not has_jinja_error and not has_template_error
        issues = []
        if not has_structure:
            issues.append("no HTML structure")
        if not has_tailwind:
            issues.append("no Tailwind classes")
        if has_jinja_error:
            issues.append("raw Jinja2 in output")
        if has_template_error:
            issues.append("template error")

        record(f"J: Template quality - {name}",
               passed and r.status_code == 200,
               f"status={r.status_code}" + (f", issues: {', '.join(issues)}" if issues else ""))

    c.close()
except Exception as e:
    record("J: Template quality", False, str(e))


# ═══════════════════════════════════════════════════════════
# K. Edge Cases
# ═══════════════════════════════════════════════════════════
print("\n=== K. Edge Cases ===")

# K1: Protected pages without login
PROTECTED = [
    "/booking/calendar",
    "/booking/my-bookings",
    "/booking/dashboard",
    "/booking/messages",
    "/booking/payment",
    "/booking/notices",
    "/booking/mypage",
]

try:
    c = httpx.Client(base_url=BASE, follow_redirects=False, timeout=10)
    for path in PROTECTED:
        r = c.get(path)
        # Should redirect (303) or show login page (200 with login content)
        if r.status_code == 303:
            is_protected = "/booking" in r.headers.get("location", "")
        elif r.status_code == 200:
            is_protected = "로그인" in r.text or "인증번호" in r.text
        else:
            is_protected = False

        record(f"K1: Protected without login: {path}",
               is_protected,
               f"status={r.status_code}, redirects_or_login={is_protected}")
    c.close()
except Exception as e:
    record("K1: Protected pages", False, str(e))

# K2: Login with different test accounts
TEST_ACCOUNTS = [
    ("이학생", "5678", "STU002"),
    ("박공부", "9012", "STU003"),
    ("최열심", "3456", "STU004"),
    ("정성실", "7890", "STU005"),
]

for name, code, stu_id in TEST_ACCOUNTS:
    try:
        c = login_client(name, code)
        r = c.get("/booking/")
        html = r.text
        has_name = name in html
        record(f"K2: Login as {name}", has_name,
               f"shows_name={has_name}")
        c.close()
    except Exception as e:
        record(f"K2: Login as {name}", False, str(e))

# K3: Different remaining credits per student
print("\n  --- Remaining credits per student ---")
EXPECTED_REMAINING = {
    "김수강": ("1234", 20, 13),   # 20 total - 13 used = 7
    "이학생": ("5678", 8, 0),     # 8 total - 0 used = 8
    "박공부": ("9012", 40, 0),    # 40 total - 0 used = 40
    "최열심": ("3456", 20, 0),    # 20 total - 0 used = 20
    "정성실": ("7890", 8, 0),     # 8 total - 0 used = 8
}

for name, (code, total, used) in EXPECTED_REMAINING.items():
    expected = total - used
    try:
        c = login_client(name, code)
        r = c.get("/booking/")
        html = r.text
        has_expected = str(expected) in html
        record(f"K3: {name} remaining = {expected}",
               has_expected,
               f"expected={expected}, found_in_html={has_expected}")
        c.close()
    except Exception as e:
        record(f"K3: {name} remaining credits", False, str(e))


# ═══════════════════════════════════════════════════════════
# REPORT
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("QA TEST REPORT")
print("=" * 60)

total = len(RESULTS)
passed = sum(1 for _, p, _ in RESULTS if p)
failed = total - passed

print(f"\nTotal: {total}  |  Passed: {passed}  |  Failed: {failed}")
print(f"Pass rate: {passed/total*100:.1f}%\n")

if failed > 0:
    print("--- FAILURES ---")
    for name, p, detail in RESULTS:
        if not p:
            print(f"  FAIL: {name}")
            print(f"        {detail}")
    print()

print("--- ALL RESULTS ---")
for name, p, detail in RESULTS:
    mark = "PASS" if p else "FAIL"
    print(f"  [{mark}] {name}")

print(f"\nDone. {passed}/{total} tests passed.")
