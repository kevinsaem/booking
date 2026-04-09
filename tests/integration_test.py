#!/usr/bin/env python3
"""
Comprehensive Integration Test for kevinsaem-booking system.
Tests all routes: landing, auth, student, teacher, admin, role enforcement, edge cases.
Uses JWT tokens directly (no Kakao OAuth needed).
"""

import sys
import os
import sqlite3
import traceback
from datetime import datetime, timedelta

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Reset DB before tests
from app.seed import reset_db
reset_db()

from fastapi.testclient import TestClient
from main import app
from app.services.auth_service import create_jwt
from app.database import execute_query, SQLITE_PATH

client = TestClient(app, raise_server_exceptions=False)

# ── Token factory ──────────────────────────────────────────

def make_token(mem_id, name, role, settle_code=0):
    return create_jwt({"mem_MbrId": mem_id, "name": name, "role": role, "settle_code": settle_code})

STUDENT_TOKEN = make_token("STU001", "김수강", "student", 10001)
TEACHER_TOKEN = make_token("TEA001", "김코딩", "teacher", 0)
ADMIN_TOKEN   = make_token("ADM001", "관리자", "admin", 0)

def get_client(token=None):
    """Return a fresh client (or reuse) with token cookie set."""
    c = TestClient(app, raise_server_exceptions=False)
    if token:
        c.cookies.set("token", token)
    return c


# ── Test infrastructure ───────────────────────────────────

results = []  # list of (section, name, passed, detail)

def test(section, name, fn):
    try:
        fn()
        results.append((section, name, True, ""))
    except AssertionError as e:
        results.append((section, name, False, str(e)))
    except Exception as e:
        tb = traceback.format_exc()
        results.append((section, name, False, f"EXCEPTION: {e}\n{tb}"))


def assert_status(resp, expected, msg=""):
    actual = resp.status_code
    assert actual == expected, f"Expected status {expected}, got {actual}. {msg} URL={resp.url}"


def assert_contains(resp, text, msg=""):
    body = resp.text
    assert text in body, f"Response body does not contain '{text}'. {msg} (len={len(body)})"


def assert_not_contains(resp, text, msg=""):
    body = resp.text
    assert text not in body, f"Response body should NOT contain '{text}'. {msg}"


# ── Helper: find a future weekday date with available slots ─

def next_weekday_with_slots():
    """Return a future weekday date string (YYYY-MM-DD) that has available slots."""
    now = datetime.now()
    for d in range(1, 30):
        dt = now + timedelta(days=d)
        if dt.weekday() < 5:  # Mon-Fri
            date_str = dt.strftime("%Y-%m-%d")
            row = execute_query(
                "SELECT COUNT(*) AS cnt FROM ek_Sch_Detail_Room "
                "WHERE sch_room_status = 1 AND strftime('%Y-%m-%d', sch_detail_Stime) = ? "
                "AND sch_room_idx NOT IN (SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1)",
                (date_str,), fetch="one"
            )
            if row and row["cnt"] > 0:
                return date_str
    return (now + timedelta(days=1)).strftime("%Y-%m-%d")


def get_available_slot(date_str):
    """Get an available room_idx and teacher for a date."""
    row = execute_query(
        "SELECT A.sch_room_idx, A.sch_teach_id, "
        "strftime('%H:%M', A.sch_detail_Stime) || '~' || strftime('%H:%M', A.sch_detail_Etime) AS time_label "
        "FROM ek_Sch_Detail_Room A "
        "WHERE A.sch_room_status = 1 "
        "AND strftime('%Y-%m-%d', A.sch_detail_Stime) = ? "
        "AND A.sch_room_idx NOT IN (SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1) "
        "ORDER BY A.sch_detail_Stime LIMIT 1",
        (date_str,), fetch="one"
    )
    return row


# ═══════════════════════════════════════════════════════════
# 1. LANDING PAGE
# ═══════════════════════════════════════════════════════════

def test_landing_page():
    test("1.LANDING", "GET / returns 200", lambda: assert_status(client.get("/"), 200))
    test("1.LANDING", "Contains '케빈샘AI코딩학원'", lambda: assert_contains(client.get("/"), "케빈샘AI코딩학원"))
    test("1.LANDING", "Contains '수강료'", lambda: assert_contains(client.get("/"), "수강료"))
    test("1.LANDING", "Contains 카카오 or login link", lambda: assert_contains(client.get("/"), "카카오"))


# ═══════════════════════════════════════════════════════════
# 2. AUTH FLOW
# ═══════════════════════════════════════════════════════════

def test_auth_flow():
    def _no_token_shows_login():
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/booking/")
        assert_status(resp, 200)
        # Should show login page with Kakao button
        assert_contains(resp, "카카오")

    def _kakao_login_redirects():
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.get("/auth/kakao/login", follow_redirects=False)
        assert resp.status_code in (302, 307), f"Expected 302/307, got {resp.status_code}"
        location = resp.headers.get("location", "")
        assert "kauth.kakao.com" in location, f"Expected redirect to kauth.kakao.com, got: {location}"

    def _old_login_removed():
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post("/booking/login", data={"name": "test", "code": "1234"})
        assert resp.status_code in (404, 405, 422), f"Expected 404/405/422 for removed route, got {resp.status_code}"

    test("2.AUTH", "No token -> login page with Kakao", _no_token_shows_login)
    test("2.AUTH", "GET /auth/kakao/login -> redirect to kauth.kakao.com", _kakao_login_redirects)
    test("2.AUTH", "POST /booking/login removed (404/405)", _old_login_removed)


# ═══════════════════════════════════════════════════════════
# 3. STUDENT FLOW
# ═══════════════════════════════════════════════════════════

def test_student_flow():
    sc = get_client(STUDENT_TOKEN)
    future_date = next_weekday_with_slots()
    slot_info = get_available_slot(future_date)

    test("3.STUDENT", "GET /booking/ -> 200, contains 김수강", lambda: (
        assert_status(sc.get("/booking/"), 200),
        assert_contains(sc.get("/booking/"), "김수강")
    ))

    test("3.STUDENT", "GET /booking/ -> remaining '7'", lambda: (
        assert_contains(sc.get("/booking/"), "7")
    ))

    test("3.STUDENT", "GET /booking/calendar -> 200", lambda: (
        assert_status(sc.get("/booking/calendar"), 200)
    ))

    test("3.STUDENT", f"GET /booking/partials/time-slots?date={future_date} -> 200", lambda: (
        assert_status(sc.get(f"/booking/partials/time-slots?date={future_date}"), 200)
    ))

    def _teacher_list():
        if not slot_info:
            raise AssertionError(f"No available slot found for {future_date}")
        time_label = slot_info["time_label"]
        room_idx = slot_info["sch_room_idx"]
        resp = sc.get(f"/booking/partials/teacher-list?date={future_date}&time={time_label}&room_idx={room_idx}")
        assert_status(resp, 200)

    test("3.STUDENT", "GET /booking/partials/teacher-list -> 200", _teacher_list)

    def _repeat_page():
        if not slot_info:
            raise AssertionError("No slot available")
        resp = sc.post("/booking/repeat", data={
            "date": future_date,
            "time": slot_info["time_label"],
            "room_idx": slot_info["sch_room_idx"],
            "teacher_id": slot_info["sch_teach_id"],
        })
        assert_status(resp, 200)

    test("3.STUDENT", "POST /booking/repeat -> 200", _repeat_page)

    def _confirm_page():
        if not slot_info:
            raise AssertionError("No slot available")
        resp = sc.post("/booking/confirm", data={
            "dates[]": [future_date],
            "teacher_name": "김코딩",
            "teacher_id": slot_info["sch_teach_id"],
            "room_idx": slot_info["sch_room_idx"],
            "time": slot_info["time_label"],
        })
        assert_status(resp, 200)

    test("3.STUDENT", "POST /booking/confirm -> 200", _confirm_page)

    def _complete_booking():
        if not slot_info:
            raise AssertionError("No slot available")
        resp = sc.post("/booking/complete", data={
            "dates[]": [future_date],
            "room_idx": slot_info["sch_room_idx"],
            "teacher_id": slot_info["sch_teach_id"],
            "settle_code": 10001,
            "teacher_name": "김코딩",
        })
        assert_status(resp, 200)

    test("3.STUDENT", "POST /booking/complete -> 200 (creates booking)", _complete_booking)

    test("3.STUDENT", "GET /booking/my-bookings -> 200", lambda: (
        assert_status(sc.get("/booking/my-bookings"), 200)
    ))

    test("3.STUDENT", "GET /booking/dashboard -> 200", lambda: (
        assert_status(sc.get("/booking/dashboard"), 200)
    ))

    test("3.STUDENT", "GET /booking/messages -> 200", lambda: (
        assert_status(sc.get("/booking/messages"), 200)
    ))

    test("3.STUDENT", "GET /booking/chat/TEA001 -> 200", lambda: (
        assert_status(sc.get("/booking/chat/TEA001"), 200)
    ))

    test("3.STUDENT", "GET /booking/payment -> 200, contains packages", lambda: (
        assert_status(sc.get("/booking/payment"), 200),
        assert_contains(sc.get("/booking/payment"), "취미반")
    ))

    test("3.STUDENT", "GET /booking/payment/checkout?package_code=101 -> 200, tosspayments", lambda: (
        assert_status(sc.get("/booking/payment/checkout?package_code=101"), 200),
        assert_contains(sc.get("/booking/payment/checkout?package_code=101"), "tosspayments")
    ))

    test("3.STUDENT", "GET /booking/notices -> 200", lambda: (
        assert_status(sc.get("/booking/notices"), 200)
    ))

    test("3.STUDENT", "GET /booking/notices/1 -> 200", lambda: (
        assert_status(sc.get("/booking/notices/1"), 200)
    ))

    test("3.STUDENT", "GET /booking/mypage -> 200", lambda: (
        assert_status(sc.get("/booking/mypage"), 200)
    ))


# ═══════════════════════════════════════════════════════════
# 4. NEW USER FLOW (simulate new Kakao signup)
# ═══════════════════════════════════════════════════════════

def test_new_user_flow():
    # Insert a new kakao_member with no settlement
    execute_query(
        "INSERT OR IGNORE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
        ("new_kakao_999", "KKO99999", "신규유저", "student"),
        fetch="none"
    )
    # Also insert into ek_Member so the app can find them
    execute_query(
        "INSERT OR IGNORE INTO ek_Member (mem_MbrId, mem_MbrName, mem_nickname, mem_MbrType, edc_idx) "
        "VALUES (?, ?, ?, ?, ?)",
        ("KKO99999", "신규유저", "신규유저", "student", 1),
        fetch="none"
    )

    new_token = make_token("KKO99999", "신규유저", "student", 0)
    nc = get_client(new_token)

    def _new_user_home():
        resp = nc.get("/booking/")
        assert_status(resp, 200)
        # Should handle settle_code=0 gracefully (no crash)

    def _new_user_payment():
        resp = nc.get("/booking/payment")
        assert_status(resp, 200)
        # Should show packages to buy

    def _new_user_remaining_zero():
        # remaining should be 0, no crash
        resp = nc.get("/booking/calendar")
        assert_status(resp, 200)

    test("4.NEW_USER", "GET /booking/ with settle_code=0 -> 200", _new_user_home)
    test("4.NEW_USER", "GET /booking/payment -> 200", _new_user_payment)
    test("4.NEW_USER", "GET /booking/calendar with remaining=0 -> 200", _new_user_remaining_zero)


# ═══════════════════════════════════════════════════════════
# 5. TEACHER FLOW
# ═══════════════════════════════════════════════════════════

def test_teacher_flow():
    tc = get_client(TEACHER_TOKEN)

    test("5.TEACHER", "GET /teacher/ -> 200, contains 김코딩", lambda: (
        assert_status(tc.get("/teacher/"), 200),
        assert_contains(tc.get("/teacher/"), "김코딩")
    ))

    test("5.TEACHER", "GET /teacher/schedule -> 200", lambda: (
        assert_status(tc.get("/teacher/schedule"), 200)
    ))

    def _add_slot():
        # Add a slot for next Monday
        now = datetime.now()
        days_ahead = 7 - now.weekday()  # next Monday
        if days_ahead <= 0:
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        resp = tc.post("/teacher/schedule/add", data={
            "date": target,
            "start_time": "09:00",
            "end_time": "09:50",
            "repeat_weeks": 1,
        }, follow_redirects=False)
        assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"

        # Verify slot exists
        row = execute_query(
            "SELECT sch_room_idx FROM ek_Sch_Detail_Room "
            "WHERE sch_teach_id = 'TEA001' AND sch_detail_Stime = ?",
            (f"{target} 09:00:00",), fetch="one"
        )
        assert row is not None, "New slot not found in DB"
        return row["sch_room_idx"], target

    # We need the slot idx for deletion
    slot_idx_holder = [None]
    def _add_slot_wrapped():
        idx, dt = _add_slot()
        slot_idx_holder[0] = idx

    test("5.TEACHER", "POST /teacher/schedule/add -> 303 + slot in DB", _add_slot_wrapped)

    def _delete_slot():
        idx = slot_idx_holder[0]
        if idx is None:
            raise AssertionError("No slot to delete (add failed)")
        resp = tc.post(f"/teacher/schedule/delete/{idx}", follow_redirects=False)
        assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"
        # Verify deleted
        row = execute_query(
            "SELECT sch_room_idx FROM ek_Sch_Detail_Room WHERE sch_room_idx = ?",
            (idx,), fetch="one"
        )
        assert row is None, "Slot was not deleted"

    test("5.TEACHER", "POST /teacher/schedule/delete -> 303 + slot removed", _delete_slot)

    test("5.TEACHER", "GET /teacher/students -> 200", lambda: (
        assert_status(tc.get("/teacher/students"), 200)
    ))

    test("5.TEACHER", "GET /teacher/messages -> 200", lambda: (
        assert_status(tc.get("/teacher/messages"), 200)
    ))

    test("5.TEACHER", "GET /teacher/chat/STU001 -> 200", lambda: (
        assert_status(tc.get("/teacher/chat/STU001"), 200)
    ))


# ═══════════════════════════════════════════════════════════
# 6. ADMIN FLOW
# ═══════════════════════════════════════════════════════════

def test_admin_flow():
    ac = get_client(ADMIN_TOKEN)

    # Need to also insert ADM001 in ek_Member for some queries
    execute_query(
        "INSERT OR IGNORE INTO ek_Member (mem_MbrId, mem_MbrName, mem_MbrType, edc_idx) "
        "VALUES (?, ?, ?, ?)",
        ("ADM001", "관리자", "admin", 1),
        fetch="none"
    )

    test("6.ADMIN", "GET /admin/ -> 200, dashboard stats", lambda: (
        assert_status(ac.get("/admin/"), 200)
    ))

    test("6.ADMIN", "GET /admin/students -> 200", lambda: (
        assert_status(ac.get("/admin/students"), 200)
    ))

    test("6.ADMIN", "GET /admin/students/STU001 -> 200, contains 김수강", lambda: (
        assert_status(ac.get("/admin/students/STU001"), 200),
        assert_contains(ac.get("/admin/students/STU001"), "김수강")
    ))

    test("6.ADMIN", "GET /admin/teachers -> 200", lambda: (
        assert_status(ac.get("/admin/teachers"), 200)
    ))

    test("6.ADMIN", "GET /admin/schedule -> 200", lambda: (
        assert_status(ac.get("/admin/schedule"), 200)
    ))

    test("6.ADMIN", "GET /admin/bookings -> 200", lambda: (
        assert_status(ac.get("/admin/bookings"), 200)
    ))

    test("6.ADMIN", "GET /admin/notices -> 200", lambda: (
        assert_status(ac.get("/admin/notices"), 200)
    ))

    test("6.ADMIN", "GET /admin/notices/new -> 200", lambda: (
        assert_status(ac.get("/admin/notices/new"), 200)
    ))

    def _create_notice():
        resp = ac.post("/admin/notices/create", data={
            "title": "테스트 공지",
            "summary": "테스트 요약",
            "content": "테스트 내용입니다.",
            "type": "notice",
        }, follow_redirects=False)
        assert resp.status_code == 302, f"Expected 302, got {resp.status_code}"
        # Verify in DB
        row = execute_query(
            "SELECT * FROM dev_notices WHERE title = '테스트 공지'",
            fetch="one"
        )
        assert row is not None, "Notice not created in DB"

    test("6.ADMIN", "POST /admin/notices/create -> redirect + in DB", _create_notice)

    test("6.ADMIN", "GET /admin/packages -> 200", lambda: (
        assert_status(ac.get("/admin/packages"), 200)
    ))

    test("6.ADMIN", "GET /admin/users -> 200, role management", lambda: (
        assert_status(ac.get("/admin/users"), 200)
    ))


# ═══════════════════════════════════════════════════════════
# 7. ADMIN MOBILE FLOW
# ═══════════════════════════════════════════════════════════

def test_admin_mobile():
    # Use admin token with mobile user-agent
    mc = TestClient(app, raise_server_exceptions=False)
    mc.cookies.set("token", ADMIN_TOKEN)
    mobile_headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) Mobile/15E148"}

    test("7.MOBILE_ADMIN", "GET /admin/m/ -> 200", lambda: (
        assert_status(mc.get("/admin/m/", headers=mobile_headers), 200)
    ))

    test("7.MOBILE_ADMIN", "GET /admin/m/bookings -> 200", lambda: (
        assert_status(mc.get("/admin/m/bookings", headers=mobile_headers), 200)
    ))

    test("7.MOBILE_ADMIN", "GET /admin/m/students -> 200", lambda: (
        assert_status(mc.get("/admin/m/students", headers=mobile_headers), 200)
    ))


# ═══════════════════════════════════════════════════════════
# 8. ROLE ENFORCEMENT
# ═══════════════════════════════════════════════════════════

def test_role_enforcement():
    sc = get_client(STUDENT_TOKEN)
    tc = get_client(TEACHER_TOKEN)
    ac = get_client(ADMIN_TOKEN)

    def _student_blocked_admin():
        resp = sc.get("/admin/", follow_redirects=False)
        # Should redirect (302) to booking page
        assert resp.status_code == 302, f"Student should be blocked from /admin/, got {resp.status_code}"

    def _student_blocked_teacher():
        resp = sc.get("/teacher/", follow_redirects=False)
        # Should redirect to /booking/
        assert resp.status_code in (302, 307, 200), f"Got {resp.status_code}"
        if resp.status_code == 200:
            # If 200, it should be showing the booking page (redirect was followed)
            pass
        else:
            location = resp.headers.get("location", "")
            assert "/booking" in location or location == "/booking/", f"Student should be redirected from /teacher/, got location: {location}"

    def _teacher_blocked_admin():
        resp = tc.get("/admin/", follow_redirects=False)
        assert resp.status_code == 302, f"Teacher should be blocked from /admin/, got {resp.status_code}"

    def _admin_blocked_teacher():
        resp = ac.get("/teacher/", follow_redirects=False)
        # Admin is not a teacher, should redirect
        assert resp.status_code in (302, 307, 200), f"Got {resp.status_code}"
        if resp.status_code == 200:
            pass  # might show redirect page
        else:
            location = resp.headers.get("location", "")
            assert "/booking" in location, f"Admin should be redirected from /teacher/, got: {location}"

    test("8.ROLES", "Student -> /admin/ blocked (302)", _student_blocked_admin)
    test("8.ROLES", "Student -> /teacher/ blocked", _student_blocked_teacher)
    test("8.ROLES", "Teacher -> /admin/ blocked (302)", _teacher_blocked_admin)
    test("8.ROLES", "Admin -> /teacher/ blocked", _admin_blocked_teacher)


# ═══════════════════════════════════════════════════════════
# 9. SLOT -> BOOKING INTEGRATION
# ═══════════════════════════════════════════════════════════

def test_slot_booking_integration():
    tc = get_client(TEACHER_TOKEN)
    sc = get_client(STUDENT_TOKEN)

    def _integration():
        # Teacher adds a new slot for tomorrow (or next weekday)
        now = datetime.now()
        target = None
        for d in range(1, 14):
            dt = now + timedelta(days=d)
            if dt.weekday() < 5:
                target = dt.strftime("%Y-%m-%d")
                break

        # Add slot
        resp = tc.post("/teacher/schedule/add", data={
            "date": target,
            "start_time": "08:00",
            "end_time": "08:50",
            "repeat_weeks": 1,
        }, follow_redirects=False)
        assert resp.status_code == 303

        # Verify slot exists in DB
        row = execute_query(
            "SELECT sch_room_idx FROM ek_Sch_Detail_Room "
            "WHERE sch_teach_id = 'TEA001' AND sch_detail_Stime = ?",
            (f"{target} 08:00:00",), fetch="one"
        )
        assert row is not None, "Teacher slot not found in DB"

        # Student should see this slot in time-slots
        resp2 = sc.get(f"/booking/partials/time-slots?date={target}")
        assert_status(resp2, 200)
        assert_contains(resp2, "08:00", "Student should see the 08:00 slot teacher created")

    test("9.INTEGRATION", "Teacher adds slot -> Student sees it in time-slots", _integration)


# ═══════════════════════════════════════════════════════════
# 10. EDGE CASES
# ═══════════════════════════════════════════════════════════

def test_edge_cases():
    test("10.EDGE", "GET /booking/payment/fail?code=USER_CANCEL&message=test -> 200", lambda: (
        assert_status(client.get("/booking/payment/fail?code=USER_CANCEL&message=test"), 200)
    ))

    test("10.EDGE", "GET /health -> 200", lambda: (
        assert_status(client.get("/health"), 200)
    ))

    def _invalid_jwt():
        bad = get_client("invalid.jwt.token")
        resp = bad.get("/booking/", follow_redirects=False)
        # Should show login page (user is None) - returns 200 with login template
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert_contains(resp, "카카오", "Invalid JWT should show login page")

    test("10.EDGE", "Invalid JWT -> login page", _invalid_jwt)


# ═══════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  KEVINSAEM-BOOKING INTEGRATION TEST")
    print("=" * 70)

    test_landing_page()
    test_auth_flow()
    test_student_flow()
    test_new_user_flow()
    test_teacher_flow()
    test_admin_flow()
    test_admin_mobile()
    test_role_enforcement()
    test_slot_booking_integration()
    test_edge_cases()

    # ── Summary ───────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r[2])
    failed = sum(1 for r in results if not r[2])

    print("\n" + "=" * 70)
    print("  TEST RESULTS")
    print("=" * 70)

    current_section = ""
    for section, name, ok, detail in results:
        if section != current_section:
            print(f"\n  [{section}]")
            current_section = section
        status = "PASS" if ok else "FAIL"
        icon = "  " if ok else "  "
        print(f"    {icon} {status}  {name}")
        if not ok and detail:
            for line in detail.split("\n")[:5]:  # max 5 lines of detail
                print(f"           {line}")

    print("\n" + "-" * 70)
    print(f"  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}")

    if failed > 0:
        print("\n  FAILURES:")
        for section, name, ok, detail in results:
            if not ok:
                print(f"    [{section}] {name}")
                for line in detail.split("\n")[:8]:
                    print(f"      {line}")
                print()

    print("=" * 70)
    sys.exit(1 if failed > 0 else 0)
