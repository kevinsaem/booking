# app/routers/admin_pages.py
# 관리자 웹 라우터 (Jinja2 SSR)
# URL 패턴: /admin/*
# 인증: 카카오 로그인 JWT (role='admin')

import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.database import execute_query
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/admin", tags=["관리자 웹"])
templates = Jinja2Templates(directory="templates")


# ─── 헬퍼 ────────────────────────────────────────────────

async def _require_admin(request: Request):
    """admin 역할 확인. admin이 아니면 리다이렉트 반환"""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/booking/?msg=로그인이 필요합니다&msg_type=error", status_code=302), None
    if user.get("role") != "admin":
        return RedirectResponse("/booking/?msg=관리자 권한이 필요합니다&msg_type=error", status_code=302), None
    return None, user


def _is_mobile(request: Request) -> bool:
    """User-Agent 기반 모바일 디바이스 감지"""
    ua = request.headers.get("user-agent", "")
    mobile_pattern = r"Mobile|Android|iPhone|iPad|iPod|webOS|BlackBerry|Opera Mini|IEMobile"
    return bool(re.search(mobile_pattern, ua, re.IGNORECASE))


def _flash_redirect(url: str, message: str, flash_type: str = "success"):
    """메시지와 함께 리다이렉트 (쿼리 파라미터 방식)"""
    sep = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{sep}msg={message}&msg_type={flash_type}", status_code=302)


def _get_flash(request: Request) -> dict:
    """쿼리 파라미터에서 flash 메시지 추출"""
    msg = request.query_params.get("msg")
    msg_type = request.query_params.get("msg_type", "success")
    if msg:
        return {"flash_message": msg, "flash_type": msg_type}
    return {}


# ─── 인증 ─────────────────────────────────────────────────

@router.post("/logout")
async def admin_logout():
    response = RedirectResponse("/booking/", status_code=302)
    response.delete_cookie("token")
    return response


# ─── 대시보드 ──────────────────────────────────────────────

@router.get("/")
async def admin_dashboard(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    # 모바일 디바이스 감지 → 모바일 관리자 페이지로 리다이렉트
    if _is_mobile(request):
        return RedirectResponse("/admin/m/", status_code=302)

    today = datetime.now().strftime("%Y-%m-%d")
    month_start = datetime.now().strftime("%Y-%m-01")

    # 통계
    total_students = execute_query(
        "SELECT COUNT(*) as cnt FROM ek_Member WHERE mem_MbrType = '2'",
        fetch="one"
    )
    active_students = execute_query(
        "SELECT COUNT(DISTINCT s.settle_mbr_id) as cnt FROM ek_Settlement s WHERE s.settle_state = 1 AND s.settle_edate >= ?",
        (today,), fetch="one"
    )
    today_bookings = execute_query(
        "SELECT COUNT(*) as cnt FROM ek_Sch_Detail_Room_mem WHERE l_s_date LIKE ? AND status = 1",
        (f"{today}%",), fetch="one"
    )
    month_revenue = execute_query(
        "SELECT COALESCE(SUM(settle_amount), 0) as total FROM ek_Settlement WHERE settle_date >= ?",
        (month_start,), fetch="one"
    )

    stats = {
        "total_students": total_students["cnt"] if total_students else 0,
        "active_students": active_students["cnt"] if active_students else 0,
        "today_bookings": today_bookings["cnt"] if today_bookings else 0,
        "month_revenue": month_revenue["total"] if month_revenue else 0,
    }

    # 최근 예약 10건
    recent_bookings = execute_query("""
        SELECT rm.idx, rm.mem_mbrid, rm.l_s_date, rm.l_f_date, rm.status,
               m.mem_MbrName,
               t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room_mem rm
        LEFT JOIN ek_Member m ON rm.mem_mbrid = m.mem_MbrId
        LEFT JOIN ek_Sch_Detail_Room r ON rm.sch_room_idx = r.sch_room_idx
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        ORDER BY rm.idx DESC
        LIMIT 10
    """)

    ctx = {
        "active_menu": "dashboard",
        "stats": stats,
        "recent_bookings": recent_bookings,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/dashboard.html", ctx)


# ─── 사용자 관리 ──────────────────────────────────────────

@router.get("/users")
async def admin_users(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    users = execute_query(
        "SELECT mem_MbrId as mem_id, mem_MbrName as nickname, mem_MbrType, mem_edate as created_at FROM ek_Member ORDER BY mem_edate DESC"
    )

    ctx = {
        "active_menu": "users",
        "users": users,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/users.html", ctx)


@router.post("/users/{mem_id}/role")
async def admin_change_role(request: Request, mem_id: str, role: str = Form(...)):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    # 역할 값 검증
    if role not in ("student", "teacher", "admin"):
        return _flash_redirect("/admin/users", "잘못된 역할입니다", "error")

    # 자기 자신의 역할은 변경 불가
    if mem_id == user["mem_MbrId"]:
        return _flash_redirect("/admin/users", "자신의 역할은 변경할 수 없습니다", "error")

    execute_query(
        "UPDATE ek_Member SET mem_MbrType = ? WHERE mem_MbrId = ?",
        (role, mem_id),
        fetch="none"
    )
    return _flash_redirect("/admin/users", f"역할이 '{role}'로 변경되었습니다")


# ─── 수강생 ───────────────────────────────────────────────

@router.get("/students")
async def admin_students(request: Request, q: str = Query(default=None)):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    today = datetime.now().strftime("%Y-%m-%d")

    if q:
        students = execute_query("""
            SELECT m.mem_MbrId, m.mem_MbrName, m.mem_TelNo3,
                   p.package_name,
                   s.settle_state,
                   CASE WHEN s.settle_state = 1 THEN
                       p.class_cnt - COALESCE((SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem rm WHERE rm.settle_code = s.settle_code AND rm.status = 1), 0)
                   ELSE NULL END as remaining
            FROM ek_Member m
            LEFT JOIN ek_Settlement s ON m.mem_MbrId = s.settle_mbr_id AND s.settle_state = 1
            LEFT JOIN ek_Package p ON s.settle_package_code = p.package_code
            WHERE m.mem_MbrType = '2'
              AND (m.mem_MbrName LIKE ? OR m.mem_MbrId LIKE ?)
            ORDER BY m.mem_MbrName
        """, (f"%{q}%", f"%{q}%"))
    else:
        students = execute_query("""
            SELECT m.mem_MbrId, m.mem_MbrName, m.mem_TelNo3,
                   p.package_name,
                   s.settle_state,
                   CASE WHEN s.settle_state = 1 THEN
                       p.class_cnt - COALESCE((SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem rm WHERE rm.settle_code = s.settle_code AND rm.status = 1), 0)
                   ELSE NULL END as remaining
            FROM ek_Member m
            LEFT JOIN ek_Settlement s ON m.mem_MbrId = s.settle_mbr_id AND s.settle_state = 1
            LEFT JOIN ek_Package p ON s.settle_package_code = p.package_code
            WHERE m.mem_MbrType = '2'
            ORDER BY m.mem_MbrName
        """)

    ctx = {"active_menu": "students", "students": students, "q": q}
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/students.html", ctx)


@router.get("/students/{mem_id}")
async def admin_student_detail(request: Request, mem_id: str):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    student = execute_query("""
        SELECT m.*, e.edc_Name as campus_name
        FROM ek_Member m
        LEFT JOIN ek_EduCenter e ON m.edc_idx = e.edc_Idx
        WHERE m.mem_MbrId = ?
    """, (mem_id,), fetch="one")

    if not student:
        return _flash_redirect("/admin/students", "수강생을 찾을 수 없습니다", "error")

    settlements = execute_query("""
        SELECT s.*, p.package_name, p.class_cnt
        FROM ek_Settlement s
        LEFT JOIN ek_Package p ON s.settle_package_code = p.package_code
        WHERE s.settle_mbr_id = ?
        ORDER BY s.settle_date DESC
    """, (mem_id,))

    bookings = execute_query("""
        SELECT rm.*, t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room_mem rm
        LEFT JOIN ek_Sch_Detail_Room r ON rm.sch_room_idx = r.sch_room_idx
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        WHERE rm.mem_mbrid = ?
        ORDER BY rm.l_s_date DESC
    """, (mem_id,))

    ctx = {
        "active_menu": "students",
        "student": student,
        "settlements": settlements,
        "bookings": bookings,
    }
    return templates.TemplateResponse(request, "admin/student_detail.html", ctx)


# ─── 강사 ─────────────────────────────────────────────────

@router.get("/teachers")
async def admin_teachers(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    teachers = execute_query("""
        SELECT m.*, e.edc_Name as campus_name
        FROM ek_Member m
        LEFT JOIN ek_EduCenter e ON m.edc_idx = e.edc_Idx
        WHERE m.mem_MbrType = '4'
        ORDER BY m.mem_MbrName
    """)

    ctx = {"active_menu": "teachers", "teachers": teachers}
    return templates.TemplateResponse(request, "admin/teachers.html", ctx)


# ─── 시간표 ───────────────────────────────────────────────

@router.get("/schedule")
async def admin_schedule(request: Request, date: str = Query(default=None)):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    selected_date = date or datetime.now().strftime("%Y-%m-%d")

    slots = execute_query("""
        SELECT r.*, t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room r
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        WHERE r.sch_detail_Stime LIKE ?
        ORDER BY r.sch_detail_Stime, t.mem_MbrName
    """, (f"{selected_date}%",))

    teachers = execute_query(
        "SELECT mem_MbrId, mem_MbrName FROM ek_Member WHERE mem_MbrType = '4' ORDER BY mem_MbrName"
    )

    ctx = {
        "active_menu": "schedule",
        "slots": slots,
        "teachers": teachers,
        "selected_date": selected_date,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/schedule.html", ctx)


@router.post("/schedule/add")
async def admin_schedule_add(
    request: Request,
    teacher_id: str = Form(...),
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    stime = f"{date} {start_time}:00"
    etime = f"{date} {end_time}:00"

    execute_query("""
        INSERT INTO ek_Sch_Detail_Room (sch_teach_id, sch_detail_Stime, sch_detail_Etime, sch_room_status, edc_idx)
        VALUES (?, ?, ?, 1, 1)
    """, (teacher_id, stime, etime), fetch="none")

    return _flash_redirect(f"/admin/schedule?date={date}", "슬롯이 추가되었습니다")


@router.post("/schedule/delete/{idx}")
async def admin_schedule_delete(request: Request, idx: int, redirect_date: str = Form(default=None)):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    # 예약이 있는 슬롯은 삭제 불가
    booking_count = execute_query(
        "SELECT COUNT(*) as cnt FROM ek_Sch_Detail_Room_mem WHERE sch_room_idx = ? AND status = 1",
        (idx,), fetch="one"
    )
    if booking_count and booking_count["cnt"] > 0:
        date_param = f"?date={redirect_date}" if redirect_date else ""
        return _flash_redirect(f"/admin/schedule{date_param}", "예약이 있는 슬롯은 삭제할 수 없습니다", "error")

    execute_query("DELETE FROM ek_Sch_Detail_Room WHERE sch_room_idx = ?", (idx,), fetch="none")
    date_param = f"?date={redirect_date}" if redirect_date else ""
    return _flash_redirect(f"/admin/schedule{date_param}", "슬롯이 삭제되었습니다")


# ─── 예약 ─────────────────────────────────────────────────

@router.get("/bookings")
async def admin_bookings(request: Request, date: str = Query(default=None), status: str = Query(default=None)):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    conditions = []
    params = []

    if date:
        conditions.append("rm.l_s_date LIKE ?")
        params.append(f"{date}%")
    if status is not None and status != "":
        conditions.append("rm.status = ?")
        params.append(int(status))

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    bookings = execute_query(f"""
        SELECT rm.idx, rm.mem_mbrid, rm.l_s_date, rm.l_f_date, rm.status,
               m.mem_MbrName,
               t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room_mem rm
        LEFT JOIN ek_Member m ON rm.mem_mbrid = m.mem_MbrId
        LEFT JOIN ek_Sch_Detail_Room r ON rm.sch_room_idx = r.sch_room_idx
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        {where}
        ORDER BY rm.l_s_date DESC
    """, params if params else None)

    ctx = {
        "active_menu": "bookings",
        "bookings": bookings,
        "selected_date": date,
        "selected_status": status,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/bookings.html", ctx)


@router.post("/bookings/cancel/{idx}")
async def admin_booking_cancel(request: Request, idx: int):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    execute_query(
        "UPDATE ek_Sch_Detail_Room_mem SET status = 0 WHERE idx = ?",
        (idx,), fetch="none"
    )
    return _flash_redirect("/admin/bookings", "예약이 취소되었습니다")


# ─── 공지사항 ──────────────────────────────────────────────

@router.get("/notices")
async def admin_notices(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    notices = execute_query(
        "SELECT * FROM dev_notices ORDER BY created_at DESC"
    )

    ctx = {"active_menu": "notices", "notices": notices}
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/notices.html", ctx)


@router.get("/notices/new")
async def admin_notice_new(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    ctx = {"active_menu": "notices", "notice": None}
    return templates.TemplateResponse(request, "admin/notice_form.html", ctx)


@router.post("/notices/create")
async def admin_notice_create(
    request: Request,
    title: str = Form(...),
    summary: str = Form(default=""),
    content: str = Form(default=""),
    type: str = Form(default="notice"),
    is_new: str = Form(default=None),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    now = datetime.now().strftime("%Y-%m-%d")
    is_new_val = 1 if is_new else 0

    execute_query("""
        INSERT INTO dev_notices (title, summary, content, type, created_at, is_new)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, summary, content, type, now, is_new_val), fetch="none")

    return _flash_redirect("/admin/notices", "공지가 작성되었습니다")


@router.get("/notices/edit/{notice_id}")
async def admin_notice_edit(request: Request, notice_id: int):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    notice = execute_query(
        "SELECT * FROM dev_notices WHERE notice_id = ?",
        (notice_id,), fetch="one"
    )
    if not notice:
        return _flash_redirect("/admin/notices", "공지를 찾을 수 없습니다", "error")

    ctx = {"active_menu": "notices", "notice": notice}
    return templates.TemplateResponse(request, "admin/notice_form.html", ctx)


@router.post("/notices/update/{notice_id}")
async def admin_notice_update(
    request: Request,
    notice_id: int,
    title: str = Form(...),
    summary: str = Form(default=""),
    content: str = Form(default=""),
    type: str = Form(default="notice"),
    is_new: str = Form(default=None),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    is_new_val = 1 if is_new else 0

    execute_query("""
        UPDATE dev_notices SET title = ?, summary = ?, content = ?, type = ?, is_new = ?
        WHERE notice_id = ?
    """, (title, summary, content, type, is_new_val, notice_id), fetch="none")

    return _flash_redirect("/admin/notices", "공지가 수정되었습니다")


@router.post("/notices/delete/{notice_id}")
async def admin_notice_delete(request: Request, notice_id: int):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    execute_query("DELETE FROM dev_notices WHERE notice_id = ?", (notice_id,), fetch="none")
    return _flash_redirect("/admin/notices", "공지가 삭제되었습니다")


# ─── 패키지 ───────────────────────────────────────────────

@router.get("/packages")
async def admin_packages(request: Request):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    packages = execute_query("SELECT * FROM ek_Package ORDER BY package_code")

    ctx = {"active_menu": "packages", "packages": packages}
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/packages.html", ctx)


@router.post("/packages/update/{code}")
async def admin_package_update(
    request: Request,
    code: int,
    class_cnt: int = Form(...),
    price: int = Form(...),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    execute_query(
        "UPDATE ek_Package SET class_cnt = ?, price = ? WHERE package_code = ?",
        (class_cnt, price, code), fetch="none"
    )
    return _flash_redirect("/admin/packages", "패키지가 수정되었습니다")


# ===== 모바일 관리자 =====

@router.get("/m/", response_class=HTMLResponse)
async def mobile_dashboard(request: Request):
    """모바일 관리자 대시보드"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    today = datetime.now().strftime("%Y-%m-%d")
    month_start = datetime.now().strftime("%Y-%m-01")
    today_display = datetime.now().strftime("%Y년 %m월 %d일")

    # 통계
    total_students = execute_query(
        "SELECT COUNT(*) as cnt FROM ek_Member WHERE mem_MbrType = '2'",
        fetch="one"
    )
    active_students = execute_query(
        "SELECT COUNT(DISTINCT s.settle_mbr_id) as cnt FROM ek_Settlement s WHERE s.settle_state = 1 AND s.settle_edate >= ?",
        (today,), fetch="one"
    )
    today_bookings_cnt = execute_query(
        "SELECT COUNT(*) as cnt FROM ek_Sch_Detail_Room_mem WHERE l_s_date LIKE ? AND status = 1",
        (f"{today}%",), fetch="one"
    )
    month_revenue = execute_query(
        "SELECT COALESCE(SUM(settle_amount), 0) as total FROM ek_Settlement WHERE settle_date >= ?",
        (month_start,), fetch="one"
    )

    stats = {
        "total_students": total_students["cnt"] if total_students else 0,
        "active_students": active_students["cnt"] if active_students else 0,
        "today_bookings": today_bookings_cnt["cnt"] if today_bookings_cnt else 0,
        "month_revenue": month_revenue["total"] if month_revenue else 0,
    }

    # 오늘 예약 목록
    today_bookings = execute_query("""
        SELECT rm.idx, rm.mem_mbrid, rm.l_s_date, rm.l_f_date, rm.status,
               m.mem_MbrName,
               t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room_mem rm
        LEFT JOIN ek_Member m ON rm.mem_mbrid = m.mem_MbrId
        LEFT JOIN ek_Sch_Detail_Room r ON rm.sch_room_idx = r.sch_room_idx
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        WHERE rm.l_s_date LIKE ?
        ORDER BY rm.l_s_date ASC
    """, (f"{today}%",))

    ctx = {
        "active_tab": "home",
        "stats": stats,
        "today_bookings": today_bookings,
        "today_display": today_display,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/mobile/dashboard.html", ctx)


@router.get("/m/bookings", response_class=HTMLResponse)
async def mobile_bookings(request: Request, date: str = Query(default=None)):
    """모바일 예약 관리"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    selected_date = date or today

    bookings = execute_query("""
        SELECT rm.idx, rm.mem_mbrid, rm.l_s_date, rm.l_f_date, rm.status,
               m.mem_MbrName,
               t.mem_MbrName as teacher_name
        FROM ek_Sch_Detail_Room_mem rm
        LEFT JOIN ek_Member m ON rm.mem_mbrid = m.mem_MbrId
        LEFT JOIN ek_Sch_Detail_Room r ON rm.sch_room_idx = r.sch_room_idx
        LEFT JOIN ek_Member t ON r.sch_teach_id = t.mem_MbrId
        WHERE rm.l_s_date LIKE ?
        ORDER BY rm.l_s_date ASC
    """, (f"{selected_date}%",))

    ctx = {
        "active_tab": "bookings",
        "bookings": bookings,
        "today": today,
        "tomorrow": tomorrow,
        "selected_date": selected_date,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/mobile/bookings.html", ctx)


@router.get("/m/students", response_class=HTMLResponse)
async def mobile_students(request: Request, q: str = Query(default=None)):
    """모바일 수강생 조회"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    if q:
        students = execute_query("""
            SELECT m.mem_MbrId, m.mem_MbrName, m.mem_TelNo3,
                   p.package_name,
                   s.settle_state,
                   CASE WHEN s.settle_state = 1 THEN
                       p.class_cnt - COALESCE((SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem rm WHERE rm.settle_code = s.settle_code AND rm.status = 1), 0)
                   ELSE NULL END as remaining
            FROM ek_Member m
            LEFT JOIN ek_Settlement s ON m.mem_MbrId = s.settle_mbr_id AND s.settle_state = 1
            LEFT JOIN ek_Package p ON s.settle_package_code = p.package_code
            WHERE m.mem_MbrType = '2'
              AND (m.mem_MbrName LIKE ? OR m.mem_MbrId LIKE ?)
            ORDER BY m.mem_MbrName
        """, (f"%{q}%", f"%{q}%"))
    else:
        students = execute_query("""
            SELECT m.mem_MbrId, m.mem_MbrName, m.mem_TelNo3,
                   p.package_name,
                   s.settle_state,
                   CASE WHEN s.settle_state = 1 THEN
                       p.class_cnt - COALESCE((SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem rm WHERE rm.settle_code = s.settle_code AND rm.status = 1), 0)
                   ELSE NULL END as remaining
            FROM ek_Member m
            LEFT JOIN ek_Settlement s ON m.mem_MbrId = s.settle_mbr_id AND s.settle_state = 1
            LEFT JOIN ek_Package p ON s.settle_package_code = p.package_code
            WHERE m.mem_MbrType = '2'
            ORDER BY m.mem_MbrName
        """)

    ctx = {
        "active_tab": "students",
        "students": students,
        "q": q,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/mobile/students.html", ctx)
