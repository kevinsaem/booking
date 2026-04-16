# app/routers/admin_pages.py
# 관리자 웹 라우터 (Jinja2 SSR)
# URL 패턴: /admin/*
# 인증: 카카오 로그인 JWT (role='admin')

import os
import re
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form, Query, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import execute_query
from app.services.auth_service import get_current_user

CAMPUS_PHOTO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "site", "images", "campus")
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

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
    from urllib.parse import quote
    sep = "&" if "?" in url else "?"
    return RedirectResponse(f"{url}{sep}msg={quote(message)}&msg_type={flash_type}", status_code=302)


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
        "SELECT board_idx AS notice_id, board_title AS title, board_content AS content, "
        "board_Wdate AS created_at FROM ek_Board WHERE board_code = '1' ORDER BY board_Wdate DESC"
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
    content: str = Form(default=""),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    now = datetime.now().strftime("%Y-%m-%d")
    mem_id = user.get("mem_MbrId", "admin")

    execute_query("""
        INSERT INTO ek_Board (board_code, board_title, board_content, board_mem_id, board_Wdate)
        VALUES ('1', ?, ?, ?, ?)
    """, (title, content, mem_id, now), fetch="none")

    return _flash_redirect("/admin/notices", "공지가 작성되었습니다")


@router.get("/notices/edit/{notice_id}")
async def admin_notice_edit(request: Request, notice_id: int):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    notice = execute_query(
        "SELECT board_idx AS notice_id, board_title AS title, board_content AS content, "
        "board_Wdate AS created_at FROM ek_Board WHERE board_idx = ? AND board_code = '1'",
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
    content: str = Form(default=""),
):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    execute_query("""
        UPDATE ek_Board SET board_title = ?, board_content = ?
        WHERE board_idx = ? AND board_code = '1'
    """, (title, content, notice_id), fetch="none")

    return _flash_redirect("/admin/notices", "공지가 수정되었습니다")


@router.post("/notices/delete/{notice_id}")
async def admin_notice_delete(request: Request, notice_id: int):
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    execute_query("DELETE FROM ek_Board WHERE board_idx = ? AND board_code = '1'", (notice_id,), fetch="none")
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


# ─── 캠퍼스 관리 ──────────────────────────────────────────

@router.get("/campuses")
async def admin_campuses(request: Request):
    """캠퍼스 목록 (사진 수 포함)"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    campuses = execute_query("""
        SELECT e.*,
               COALESCE(p.photo_count, 0) AS photo_count
        FROM ek_EduCenter e
        LEFT JOIN (
            SELECT edc_idx, COUNT(*) AS photo_count
            FROM ek_CampusPhoto
            GROUP BY edc_idx
        ) p ON e.edc_Idx = p.edc_idx
        ORDER BY e.edc_SortOrder ASC, e.edc_Idx ASC
    """)

    ctx = {
        "active_menu": "campuses",
        "campuses": campuses,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/campuses.html", ctx)


@router.get("/campuses/new")
async def admin_campus_new(request: Request):
    """캠퍼스 생성 폼"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    ctx = {
        "active_menu": "campuses",
        "campus": None,
        "photos": [],
        "admin_user": user,
    }
    return templates.TemplateResponse(request, "admin/campus_form.html", ctx)


@router.post("/campuses/create")
async def admin_campus_create(
    request: Request,
    edc_Name: str = Form(...),
    edc_Status: str = Form(default="active"),
    edc_Address: str = Form(default=""),
    edc_Phone: str = Form(default=""),
    edc_Hours: str = Form(default=""),
    edc_Description: str = Form(default=""),
    edc_Facilities: str = Form(default=""),
    edc_KakaoLink: str = Form(default=""),
    edc_BookingLink: str = Form(default=""),
    edc_MapLink: str = Form(default=""),
    edc_IsMain: int = Form(default=0),
    edc_SortOrder: int = Form(default=0),
):
    """캠퍼스 생성"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    try:
        execute_query("""
            INSERT INTO ek_EduCenter (
                edc_Name, edc_Status, edc_Address, edc_Phone, edc_Hours,
                edc_Description, edc_Facilities, edc_KakaoLink, edc_BookingLink,
                edc_MapLink, edc_IsMain, edc_SortOrder
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            edc_Name, edc_Status, edc_Address, edc_Phone, edc_Hours,
            edc_Description, edc_Facilities, edc_KakaoLink, edc_BookingLink,
            edc_MapLink, edc_IsMain, edc_SortOrder,
        ), fetch="none")
        return _flash_redirect("/admin/campuses", "캠퍼스가 등록되었습니다")
    except Exception as e:
        print(f"⚠️ 캠퍼스 생성 실패: {e}")
        return _flash_redirect("/admin/campuses", "캠퍼스 등록에 실패했습니다", "error")


@router.get("/campuses/edit/{campus_id}")
async def admin_campus_edit(request: Request, campus_id: int):
    """캠퍼스 수정 폼 (기존 데이터 + 사진)"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    campus = execute_query(
        "SELECT * FROM ek_EduCenter WHERE edc_Idx = ?",
        (campus_id,), fetch="one"
    )
    if not campus:
        return _flash_redirect("/admin/campuses", "캠퍼스를 찾을 수 없습니다", "error")

    photos = execute_query(
        "SELECT * FROM ek_CampusPhoto WHERE edc_idx = ? ORDER BY sort_order ASC, photo_id ASC",
        (campus_id,)
    )

    ctx = {
        "active_menu": "campuses",
        "campus": campus,
        "photos": photos,
        "admin_user": user,
    }
    ctx.update(_get_flash(request))
    return templates.TemplateResponse(request, "admin/campus_form.html", ctx)


@router.post("/campuses/update/{campus_id}")
async def admin_campus_update(
    request: Request,
    campus_id: int,
    edc_Name: str = Form(...),
    edc_Status: str = Form(default="active"),
    edc_Address: str = Form(default=""),
    edc_Phone: str = Form(default=""),
    edc_Hours: str = Form(default=""),
    edc_Description: str = Form(default=""),
    edc_Facilities: str = Form(default=""),
    edc_KakaoLink: str = Form(default=""),
    edc_BookingLink: str = Form(default=""),
    edc_MapLink: str = Form(default=""),
    edc_IsMain: int = Form(default=0),
    edc_SortOrder: int = Form(default=0),
):
    """캠퍼스 정보 수정"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    try:
        execute_query("""
            UPDATE ek_EduCenter SET
                edc_Name = ?, edc_Status = ?, edc_Address = ?, edc_Phone = ?,
                edc_Hours = ?, edc_Description = ?, edc_Facilities = ?,
                edc_KakaoLink = ?, edc_BookingLink = ?, edc_MapLink = ?,
                edc_IsMain = ?, edc_SortOrder = ?
            WHERE edc_Idx = ?
        """, (
            edc_Name, edc_Status, edc_Address, edc_Phone,
            edc_Hours, edc_Description, edc_Facilities,
            edc_KakaoLink, edc_BookingLink, edc_MapLink,
            edc_IsMain, edc_SortOrder, campus_id,
        ), fetch="none")
        return _flash_redirect(f"/admin/campuses/edit/{campus_id}", "캠퍼스 정보가 수정되었습니다")
    except Exception as e:
        print(f"⚠️ 캠퍼스 수정 실패: {e}")
        return _flash_redirect(f"/admin/campuses/edit/{campus_id}", "캠퍼스 수정에 실패했습니다", "error")


@router.post("/campuses/delete/{campus_id}")
async def admin_campus_delete(request: Request, campus_id: int):
    """캠퍼스 삭제 (사진 파일 + DB 레코드 함께 삭제)"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    try:
        # 연결된 사진 파일 삭제
        photos = execute_query(
            "SELECT photo_id, file_path FROM ek_CampusPhoto WHERE edc_idx = ?",
            (campus_id,)
        )
        for photo in photos:
            file_full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                photo["file_path"].lstrip("/")
            )
            if os.path.exists(file_full_path):
                os.remove(file_full_path)

        # DB에서 사진 레코드 삭제
        execute_query(
            "DELETE FROM ek_CampusPhoto WHERE edc_idx = ?",
            (campus_id,), fetch="none"
        )
        # DB에서 캠퍼스 삭제
        execute_query(
            "DELETE FROM ek_EduCenter WHERE edc_Idx = ?",
            (campus_id,), fetch="none"
        )
        return _flash_redirect("/admin/campuses", "캠퍼스가 삭제되었습니다")
    except Exception as e:
        print(f"⚠️ 캠퍼스 삭제 실패: {e}")
        return _flash_redirect("/admin/campuses", "캠퍼스 삭제에 실패했습니다", "error")


@router.post("/campuses/{campus_id}/photos")
async def admin_campus_photo_upload(
    request: Request,
    campus_id: int,
    files: list[UploadFile] = File(...),
):
    """캠퍼스 사진 업로드 (복수 파일)"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    # 캠퍼스 존재 확인
    campus = execute_query(
        "SELECT edc_Idx FROM ek_EduCenter WHERE edc_Idx = ?",
        (campus_id,), fetch="one"
    )
    if not campus:
        return _flash_redirect("/admin/campuses", "캠퍼스를 찾을 수 없습니다", "error")

    # 업로드 디렉토리 확보
    os.makedirs(CAMPUS_PHOTO_DIR, exist_ok=True)

    # 현재 최대 sort_order 조회
    max_order = execute_query(
        "SELECT COALESCE(MAX(sort_order), 0) AS max_order FROM ek_CampusPhoto WHERE edc_idx = ?",
        (campus_id,), fetch="one"
    )
    current_order = max_order["max_order"] if max_order else 0

    uploaded = 0
    errors = []

    for f in files:
        # 파일 타입 검증
        if f.content_type not in ALLOWED_IMAGE_TYPES:
            errors.append(f"{f.filename}: 허용되지 않는 파일 형식 ({f.content_type})")
            continue

        # 파일 읽기 + 크기 검증
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            errors.append(f"{f.filename}: 파일 크기 초과 (최대 5MB)")
            continue

        # 고유 파일명 생성
        ext = os.path.splitext(f.filename)[1].lower() if f.filename else ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        unique_name = f"{campus_id}_{uuid.uuid4().hex[:12]}{ext}"
        save_path = os.path.join(CAMPUS_PHOTO_DIR, unique_name)

        # 파일 저장
        try:
            with open(save_path, "wb") as out:
                out.write(content)
        except Exception as e:
            errors.append(f"{f.filename}: 저장 실패 ({e})")
            continue

        # DB에 레코드 삽입
        current_order += 1
        db_path = f"static/site/images/campus/{unique_name}"
        alt_text = os.path.splitext(f.filename)[0] if f.filename else ""

        try:
            execute_query("""
                INSERT INTO ek_CampusPhoto (edc_idx, file_path, alt_text, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                campus_id, db_path, alt_text, current_order,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ), fetch="none")
            uploaded += 1
        except Exception as e:
            # DB 실패 시 파일도 삭제
            if os.path.exists(save_path):
                os.remove(save_path)
            errors.append(f"{f.filename}: DB 저장 실패 ({e})")

    msg_parts = []
    if uploaded:
        msg_parts.append(f"{uploaded}개 사진 업로드 완료")
    if errors:
        msg_parts.append(f"실패: {'; '.join(errors)}")

    flash_type = "success" if uploaded and not errors else ("warning" if uploaded else "error")
    return _flash_redirect(
        f"/admin/campuses/edit/{campus_id}",
        " / ".join(msg_parts) if msg_parts else "업로드할 파일이 없습니다",
        flash_type,
    )


@router.post("/campuses/{campus_id}/photos/delete/{photo_id}")
async def admin_campus_photo_delete(request: Request, campus_id: int, photo_id: int):
    """캠퍼스 사진 개별 삭제 (파일 + DB)"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    try:
        photo = execute_query(
            "SELECT photo_id, file_path FROM ek_CampusPhoto WHERE photo_id = ? AND edc_idx = ?",
            (photo_id, campus_id), fetch="one"
        )
        if not photo:
            return _flash_redirect(f"/admin/campuses/edit/{campus_id}", "사진을 찾을 수 없습니다", "error")

        # 파일 삭제
        file_full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            photo["file_path"].lstrip("/")
        )
        if os.path.exists(file_full_path):
            os.remove(file_full_path)

        # DB 레코드 삭제
        execute_query(
            "DELETE FROM ek_CampusPhoto WHERE photo_id = ?",
            (photo_id,), fetch="none"
        )
        return _flash_redirect(f"/admin/campuses/edit/{campus_id}", "사진이 삭제되었습니다")
    except Exception as e:
        print(f"⚠️ 사진 삭제 실패: {e}")
        return _flash_redirect(f"/admin/campuses/edit/{campus_id}", "사진 삭제에 실패했습니다", "error")


@router.post("/campuses/{campus_id}/photos/reorder")
async def admin_campus_photo_reorder(request: Request, campus_id: int):
    """캠퍼스 사진 순서 변경 (JSON: {"photo_ids": [3, 1, 2]})"""
    redirect, user = await _require_admin(request)
    if redirect:
        return redirect

    try:
        body = await request.json()
        photo_ids = body.get("photo_ids", [])

        if not photo_ids:
            return JSONResponse({"ok": False, "error": "photo_ids가 비어있습니다"}, status_code=400)

        for order, pid in enumerate(photo_ids, start=1):
            execute_query(
                "UPDATE ek_CampusPhoto SET sort_order = ? WHERE photo_id = ? AND edc_idx = ?",
                (order, int(pid), campus_id), fetch="none"
            )

        return JSONResponse({"ok": True, "message": "순서가 변경되었습니다"})
    except Exception as e:
        print(f"⚠️ 사진 순서 변경 실패: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
