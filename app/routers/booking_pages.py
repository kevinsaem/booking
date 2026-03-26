# app/routers/booking_pages.py
# 수강생 웹 라우터
# Jinja2 SSR + HTMX partial 렌더링
# URL 패턴: /booking/*

import time
from datetime import datetime
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user, create_jwt
from app.services.schedule_service import (
    get_available_dates, get_time_slots, get_available_teachers,
    get_calendar_cells, get_repeat_weeks
)
from app.services.booking_service import (
    get_remaining, get_total_classes, get_settle_period, is_monthly_plan,
    create_booking, get_my_bookings, cancel_booking
)
from app.database import execute_query
from app.config import settings

router = APIRouter(prefix="/booking", tags=["수강생 웹"])
templates = Jinja2Templates(directory="templates")
partials = Jinja2Templates(directory="templates")

# 로그인 brute-force 방지: IP별 시도 기록 {ip: [(timestamp, ...), ...]}
_login_attempts: dict[str, list[float]] = {}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 15 * 60  # 15분

# ===== 페이지 라우트 =====


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, user=Depends(get_current_user)):
    """홈 페이지"""
    if not user:
        return templates.TemplateResponse(request, "booking/login.html")

    remaining = get_remaining(user["settle_code"])
    total_classes = get_total_classes(user["settle_code"])
    settle_period = get_settle_period(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])
    upcoming_bookings = get_my_bookings(user["mem_MbrId"], limit=3, upcoming=True)

    # 최신 공지 조회
    latest_notice = execute_query(
        "SELECT board_title AS title, board_content AS summary FROM ek_Board WHERE board_code = '1' ORDER BY board_Wdate DESC LIMIT 1",
        fetch="one"
    )

    # 안읽은 메시지 수 조회
    unread_count = 0
    unread_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM dev_messages "
        "WHERE receiver_id = ? AND is_read = 0",
        (user["mem_MbrId"],),
        fetch="one"
    )
    if unread_row:
        unread_count = unread_row["cnt"]

    # 멘토 피드백은 있지만 수강생 연구노트가 없는 수업 확인
    pending_note = execute_query(
        "SELECT R.idx AS booking_idx, R.sch_room_idx, "
        "datetime(R.l_s_date, '+9 hours') AS kst_start, "
        "COALESCE(M.mem_nickname, M.mem_MbrName) AS teacher_name, "
        "C.lecturede_idx, C.advice "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "JOIN ek_Member M ON A.sch_teach_id = M.mem_MbrId "
        "JOIN ek_Lecture L ON L.sch_room_idx = R.sch_room_idx AND L.mbr_id = R.mem_mbrid AND date(L.lec_date) = date(R.l_s_date) "
        "JOIN ek_LectureDe C ON C.lec_idx = L.lec_idx AND C.student_id = R.mem_mbrid "
        "WHERE R.mem_mbrid = ? AND R.status = 1 "
        "AND datetime(R.l_s_date, '+9 hours') < datetime('now', '+9 hours') "
        "AND C.advice IS NOT NULL AND C.advice != '' "
        "AND (C.report IS NULL OR C.report = '') "
        "ORDER BY R.l_s_date DESC LIMIT 1",
        (user["mem_MbrId"],),
        fetch="one"
    )

    return templates.TemplateResponse(request, "booking/home.html", {
        "user": user,
        "remaining": remaining,
        "total_classes": total_classes,
        "monthly": monthly,
        "settle_period": settle_period,
        "upcoming_bookings": upcoming_bookings,
        "unread_count": unread_count,
        "latest_notice": latest_notice,
        "pending_note": pending_note,
    })


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """회원가입 페이지"""
    return templates.TemplateResponse(request, "booking/signup.html")


@router.post("/signup", response_class=HTMLResponse)
async def do_signup(
    request: Request,
    name: str = Form(),
    email: str = Form(),
    nickname: str = Form(""),
    phone: str = Form(),
    pwd: str = Form(),
    pwd2: str = Form(),
):
    """회원가입 처리"""
    # 유효성 검사
    if not name.strip() or not email.strip() or not phone.strip():
        return templates.TemplateResponse(request, "booking/signup.html", {"error": "필수 항목을 모두 입력해주세요."})
    if len(pwd) < 4:
        return templates.TemplateResponse(request, "booking/signup.html", {"error": "비밀번호는 4자리 이상이어야 합니다."})
    if pwd != pwd2:
        return templates.TemplateResponse(request, "booking/signup.html", {"error": "비밀번호가 일치하지 않습니다."})

    # 아이디 중복 확인
    existing = execute_query(
        "SELECT mem_MbrId FROM ek_Member WHERE mem_MbrId = ?",
        (email,),
        fetch="one"
    )
    if existing:
        return templates.TemplateResponse(request, "booking/signup.html", {"error": "이미 사용 중인 이메일(아이디)입니다."})

    # ek_Member에 등록 (mem_MbrType=4: 수강생)
    execute_query(
        "INSERT INTO ek_Member "
        "(mem_MbrId, mem_MbrName, mem_nickname, mem_TelNo2, mem_TelNo3, "
        " mem_pwd, mem_MbrType, mem_edate, edc_idx) "
        "VALUES (?, ?, ?, ?, ?, ?, '4', GETDATE(), 0)",
        (email, name.strip(), nickname.strip() or name.strip(), phone, phone, pwd),
        fetch="none"
    )

    # 가입 후 자동 로그인
    user = {
        "mem_MbrId": email,
        "name": nickname.strip() or name.strip(),
        "role": "student",
        "settle_code": 0,
    }
    token = create_jwt(user)

    response = RedirectResponse("/booking/", status_code=303)
    is_prod = settings.DB_MODE == "production"
    response.set_cookie(
        "token", token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/login", response_class=HTMLResponse)
async def do_login(request: Request, name: str = Form(), code: str = Form()):
    """이름+인증번호 로그인 (역할 기반 분기)"""
    # brute-force 방지: IP별 시도 횟수 제한
    client_ip = request.client.host if request.client else "unknown"
    now_ts = time.time()
    attempts = _login_attempts.get(client_ip, [])
    # 15분 이내 시도만 남김
    attempts = [t for t in attempts if now_ts - t < _LOGIN_WINDOW_SECONDS]
    _login_attempts[client_ip] = attempts

    if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
        return templates.TemplateResponse(request, "booking/login.html", {
            "error": "로그인 시도가 너무 많습니다. 15분 후 다시 시도해주세요."
        })

    # 시도 기록
    attempts.append(now_ts)
    _login_attempts[client_ip] = attempts

    # ek_Member에서 인증
    row = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname FROM ek_Member "
        "WHERE mem_MbrName = ? AND mem_pwd = ?",
        (name, code),
        fetch="one"
    )
    if not row:
        return templates.TemplateResponse(request, "booking/login.html", {
            "error": "이름 또는 인증번호가 일치하지 않습니다."
        })

    mem_id = row["mem_MbrId"]

    # 역할은 기본 student
    role = "student"

    # 수강권 확인
    settle = execute_query(
        "SELECT settle_code FROM ek_Settlement "
        "WHERE settle_mbr_id = ? AND settle_state = 1 ORDER BY settle_date DESC",
        (mem_id,),
        fetch="one"
    )
    settle_code = settle["settle_code"] if settle else 0

    # JWT 발급
    user = {
        "mem_MbrId": mem_id,
        "name": row.get("mem_nickname") or row["mem_MbrName"],
        "role": role,
        "settle_code": settle_code,
    }
    token = create_jwt(user)

    # 역할별 분기
    redirect_map = {"admin": "/admin/", "teacher": "/teacher/", "student": "/booking/"}
    redirect_url = redirect_map.get(role, "/booking/")

    response = RedirectResponse(redirect_url, status_code=303)
    is_prod = settings.DB_MODE == "production"
    response.set_cookie(
        "token", token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/logout")
async def do_logout():
    """로그아웃"""
    response = RedirectResponse("/booking/", status_code=303)
    response.delete_cookie("token")
    return response


@router.get("/calendar", response_class=HTMLResponse)
async def booking_page(request: Request, user=Depends(get_current_user),
                       year: int = None, month: int = None):
    """수업 예약 페이지 (캘린더)"""
    if not user:
        return RedirectResponse("/booking/")

    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    remaining = get_remaining(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])

    # 횟수제이고 남은 수업 0이면 예약 불가
    if not monthly and remaining <= 0:
        return templates.TemplateResponse(request, "booking/reserve_blocked.html", {
            "user": user,
        })

    available_dates = get_available_dates(year, month, user["settle_code"])
    calendar_cells = get_calendar_cells(year, month, available_dates)

    return templates.TemplateResponse(request, "booking/reserve.html", {
        "user": user,
        "remaining": remaining,
        "year": year,
        "month": month,
        "prev_year": year if month > 1 else year - 1,
        "prev_month": month - 1 if month > 1 else 12,
        "next_year": year if month < 12 else year + 1,
        "next_month": month + 1 if month < 12 else 1,
        "calendar_cells": calendar_cells,
    })


@router.post("/repeat", response_class=HTMLResponse)
async def repeat_page(request: Request, user=Depends(get_current_user),
                      date: str = Form(), time: str = Form(),
                      room_idx: int = Form(), teacher_id: str = Form()):
    """반복 예약 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    remaining = get_remaining(user["settle_code"])
    repeat_weeks = get_repeat_weeks(date, time, room_idx, teacher_id, remaining)

    # 강사 이름 조회
    teacher = execute_query(
        "SELECT COALESCE(mem_nickname, mem_MbrName) AS name FROM ek_Member WHERE mem_MbrId = ?",
        (teacher_id,),
        fetch="one"
    )
    teacher_name = teacher["name"] if teacher else ""

    return templates.TemplateResponse(request, "booking/repeat.html", {
        "remaining": remaining,
        "repeat_weeks": repeat_weeks,
        "base_date": date,
        "time": time,
        "room_idx": room_idx,
        "teacher_id": teacher_id,
        "teacher_name": teacher_name,
    })


@router.post("/confirm", response_class=HTMLResponse)
async def confirm_page(request: Request, user=Depends(get_current_user)):
    """예약 확인 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    form = await request.form()
    dates = form.getlist("dates[]")
    remaining = get_remaining(user["settle_code"])

    return templates.TemplateResponse(request, "booking/confirm.html", {
        "user": user,
        "teacher_name": form.get("teacher_name", ""),
        "teacher_id": form.get("teacher_id"),
        "room_idx": form.get("room_idx"),
        "settle_code": user["settle_code"],
        "dates": dates,
        "dates_label": ", ".join(dates),
        "time": form.get("time"),
        "booking_count": len(dates),
        "remaining_after": remaining - len(dates),
    })


@router.post("/complete", response_class=HTMLResponse)
async def complete_page(request: Request, user=Depends(get_current_user)):
    """예약 확정 처리 + 완료 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    form = await request.form()
    dates = form.getlist("dates[]")
    room_idx = int(form.get("room_idx"))
    teacher_id = form.get("teacher_id")
    # 보안: form 대신 JWT 유저의 settle_code 사용 (타인 수강권 도용 방지)
    settle_code = user["settle_code"]

    # 예약 INSERT (서비스 레이어에서 트랜잭션 처리)
    result = create_booking(
        room_idx=room_idx,
        mem_id=user["mem_MbrId"],
        settle_code=settle_code,
        dates=dates
    )

    remaining = get_remaining(settle_code)

    # TODO: 카카오 알림톡 발송 (BackgroundTasks)

    return templates.TemplateResponse(request, "booking/complete.html", {
        "teacher_name": form.get("teacher_name", ""),
        "booking_count": len(dates),
        "remaining": remaining,
        "result": result,
    })


@router.get("/my-bookings", response_class=HTMLResponse)
async def my_bookings_page(request: Request, user=Depends(get_current_user)):
    """내 예약 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    remaining = get_remaining(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])
    total_classes = get_total_classes(user["settle_code"])
    upcoming = get_my_bookings(user["mem_MbrId"], limit=50, upcoming=True)
    past = get_my_bookings(user["mem_MbrId"], limit=50, upcoming=False)
    # past에서 확정된 과거 수업만 (취소된 건 제외)
    past_completed = [b for b in past if b["status"] == 1 and b not in upcoming]

    return templates.TemplateResponse(request, "booking/my_bookings.html", {
        "remaining": remaining,
        "monthly": monthly,
        "total_classes": total_classes,
        "upcoming": upcoming,
        "past": past_completed,
    })


@router.post("/cancel/{idx}", response_class=HTMLResponse)
async def cancel_booking_action(idx: int, request: Request, user=Depends(get_current_user)):
    """예약 취소 (HTMX partial 반환) + 멘토 알림"""
    if not user:
        return RedirectResponse("/booking/")

    # 취소 전에 멘토 정보 조회 (알림용)
    booking_info = execute_query(
        "SELECT R.idx, R.sch_room_idx, "
        "datetime(R.l_s_date, '+9 hours') AS kst_start, "
        "A.sch_teach_id, "
        "COALESCE(M.mem_nickname, M.mem_MbrName) AS teacher_name "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "JOIN ek_Member M ON A.sch_teach_id = M.mem_MbrId "
        "WHERE R.idx = ? AND R.mem_mbrid = ?",
        (idx, user["mem_MbrId"]),
        fetch="one"
    )

    result = cancel_booking(idx, user["mem_MbrId"])

    # 멘토에게 취소 알림 메시지 전송
    if result and booking_info:
        kst = booking_info.get("kst_start", "")[:16]
        msg = f"[수업 취소] {user['name']}님이 {kst} 수업을 취소했습니다."
        execute_query(
            "INSERT INTO dev_messages (sender_id, receiver_id, content, sent_at, is_read) "
            "VALUES (?, ?, ?, datetime('now'), 0)",
            (user["mem_MbrId"], booking_info["sch_teach_id"], msg),
            fetch="none"
        )

    # 취소된 예약 행을 반환 (HTMX swap)
    booking = get_my_bookings(user["mem_MbrId"], booking_idx=idx)
    return partials.TemplateResponse(request, "partials/booking_row_cancelled.html", {
        "booking": booking[0] if booking else None,
    })


# ===== HTMX Partial 라우트 =====


@router.get("/partials/calendar-grid", response_class=HTMLResponse)
async def calendar_grid_partial(request: Request, year: int, month: int,
                                user=Depends(get_current_user)):
    """캘린더 그리드 부분 렌더링"""
    if not user:
        return HTMLResponse("", status_code=401)
    available_dates = get_available_dates(year, month, user["settle_code"])
    calendar_cells = get_calendar_cells(year, month, available_dates)
    return partials.TemplateResponse(request, "partials/calendar_grid.html", {
        "calendar_cells": calendar_cells,
    })


@router.get("/partials/time-slots", response_class=HTMLResponse)
async def time_slots_partial(request: Request, date: str, user=Depends(get_current_user)):
    """시간 슬롯 부분 렌더링"""
    if not user:
        return HTMLResponse("", status_code=401)
    slots = get_time_slots(date, user["settle_code"])
    return partials.TemplateResponse(request, "partials/time_slots.html", {
        "time_slots": slots,
        "selected_date_label": date,
    })


@router.get("/partials/teacher-list", response_class=HTMLResponse)
async def teacher_list_partial(request: Request, date: str, time: str,
                               room_idx: int, user=Depends(get_current_user)):
    """강사 목록 부분 렌더링"""
    if not user:
        return HTMLResponse("", status_code=401)
    teachers = get_available_teachers(date, time, room_idx, user["settle_code"])
    return partials.TemplateResponse(request, "partials/teacher_list.html", {
        "teachers": teachers,
    })


@router.get("/partials/my-bookings-summary", response_class=HTMLResponse)
async def my_bookings_summary_partial(request: Request, user=Depends(get_current_user)):
    """홈 화면 예약 요약 부분 렌더링"""
    if not user:
        return HTMLResponse("")
    bookings = get_my_bookings(user["mem_MbrId"], limit=2, upcoming=True)
    return partials.TemplateResponse(request, "partials/my_bookings_summary.html", {
        "bookings": bookings,
    })


# ===== 추가 페이지 (학습, 메시지, 결제, 공지, MY) =====


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user=Depends(get_current_user)):
    """학습 현황 페이지 — 수업 기록 + 멘토 피드백 + 별점"""
    if not user:
        return RedirectResponse("/booking/")

    mem_id = user["mem_MbrId"]
    remaining = get_remaining(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])
    total_classes = get_total_classes(user["settle_code"])

    # 패키지명
    pkg = execute_query(
        "SELECT P.package_name FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "WHERE S.settle_code = ? AND S.settle_state = 1",
        (user["settle_code"],),
        fetch="one"
    )
    pkg_name = pkg["package_name"] if pkg else ""

    # 완료 수업 수 (과거 날짜, status=1)
    completed_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM ek_Sch_Detail_Room_mem "
        "WHERE mem_mbrid = ? AND status = 1 "
        "AND datetime(l_s_date, '+9 hours') < datetime('now', '+9 hours')",
        (mem_id,),
        fetch="one"
    )
    completed = completed_row["cnt"] if completed_row else 0

    # 수업 기록 (과거 수업, 최신순, 멘토 피드백 + 수강생 연구노트 + 별점)
    lessons = execute_query(
        "SELECT R.idx, R.sch_room_idx, "
        "datetime(R.l_s_date, '+9 hours') AS kst_start, "
        "datetime(R.l_f_date, '+9 hours') AS kst_end, "
        "COALESCE(M.mem_nickname, M.mem_MbrName) AS teacher_name, "
        "M.mem_MbrId AS teacher_id, "
        "C.advice AS feedback, "
        "C.report AS student_report, "
        "RT.rating "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "JOIN ek_Member M ON A.sch_teach_id = M.mem_MbrId "
        "LEFT JOIN ek_Lecture L ON L.sch_room_idx = R.sch_room_idx AND L.mbr_id = R.mem_mbrid AND date(L.lec_date) = date(R.l_s_date) "
        "LEFT JOIN ek_LectureDe C ON C.lec_idx = L.lec_idx AND C.student_id = R.mem_mbrid "
        "LEFT JOIN dev_mentor_rating RT ON RT.booking_idx = R.idx "
        "WHERE R.mem_mbrid = ? AND R.status = 1 "
        "AND datetime(R.l_s_date, '+9 hours') < datetime('now', '+9 hours') "
        "ORDER BY R.l_s_date DESC LIMIT 20",
        (mem_id,),
        fetch="all"
    )

    DAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
    lesson_list = []
    for l in lessons:
        dt = datetime.strptime(l["kst_start"], "%Y-%m-%d %H:%M:%S")
        edt = datetime.strptime(l["kst_end"], "%Y-%m-%d %H:%M:%S")

        lesson_list.append({
            "idx": l["idx"],
            "date_label": f"{dt.month}/{dt.day} ({DAYS_KO[dt.weekday()]})",
            "time": f"{dt.strftime('%H:%M')}~{edt.strftime('%H:%M')}",
            "teacher_name": l["teacher_name"],
            "teacher_id": l["teacher_id"],
            "feedback": l.get("feedback") or "",
            "student_report": l.get("student_report") or "",
            "rating": l.get("rating") or 0,
        })

    return templates.TemplateResponse(request, "booking/dashboard.html", {
        "user": user,
        "completed": completed,
        "remaining": remaining,
        "monthly": monthly,
        "total_classes": total_classes,
        "package_name": pkg_name,
        "lessons": lesson_list,
    })


@router.post("/dashboard/rate/{booking_idx}", response_class=HTMLResponse)
async def rate_mentor(booking_idx: int, request: Request,
                      rating: int = Form(), user=Depends(get_current_user)):
    """멘토 별점 주기"""
    if not user:
        return HTMLResponse("", status_code=401)

    mem_id = user["mem_MbrId"]

    # 본인 예약인지 확인
    booking = execute_query(
        "SELECT R.idx, A.sch_teach_id FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "WHERE R.idx = ? AND R.mem_mbrid = ?",
        (booking_idx, mem_id),
        fetch="one"
    )
    if not booking:
        return HTMLResponse("", status_code=403)

    # 별점 저장 (있으면 업데이트)
    existing = execute_query(
        "SELECT rating_id FROM dev_mentor_rating WHERE booking_idx = ?",
        (booking_idx,),
        fetch="one"
    )
    if existing:
        execute_query(
            "UPDATE dev_mentor_rating SET rating = ? WHERE booking_idx = ?",
            (rating, booking_idx),
            fetch="none"
        )
    else:
        execute_query(
            "INSERT INTO dev_mentor_rating (booking_idx, student_id, teacher_id, rating, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (booking_idx, mem_id, booking["sch_teach_id"], rating),
            fetch="none"
        )

    # 별점 HTML 반환 (HTMX swap)
    stars = ''.join([
        f'<span class="text-{"amber-400" if i < rating else "g-300"} text-[18px]">★</span>'
        for i in range(5)
    ])
    return HTMLResponse(f'<div class="flex gap-0.5">{stars}</div>')


@router.post("/dashboard/save-note", response_class=HTMLResponse)
async def save_research_note(request: Request,
                             lecturede_idx: int = Form(),
                             difficulty: str = Form(""),
                             satisfaction: str = Form(""),
                             next_topic: str = Form(""),
                             note: str = Form(""),
                             user=Depends(get_current_user)):
    """수강생 연구노트 저장"""
    if not user:
        return HTMLResponse("", status_code=401)

    # 보안: lecturede_idx가 로그인 유저의 수업인지 소유권 확인
    ownership = execute_query(
        "SELECT C.lecturede_idx FROM ek_LectureDe C "
        "JOIN ek_Lecture L ON C.lec_idx = L.lec_idx "
        "JOIN ek_Sch_Detail_Room_mem R ON R.sch_room_idx = L.sch_room_idx "
        "  AND R.mem_mbrid = L.mbr_id AND date(R.l_s_date) = date(L.lec_date) "
        "WHERE C.lecturede_idx = ? AND C.student_id = ?",
        (lecturede_idx, user["mem_MbrId"]),
        fetch="one"
    )
    if not ownership:
        return HTMLResponse("권한이 없습니다.", status_code=403)

    # 응답 조합해서 report 생성
    parts = []
    if difficulty:
        parts.append(f"[난이도] {difficulty}")
    if satisfaction:
        parts.append(f"[만족도] {satisfaction}")
    if next_topic:
        parts.append(f"[다음에 배우고 싶은 것] {next_topic}")
    if note:
        parts.append(f"\n{note}")

    report = "\n".join(parts)

    execute_query(
        "UPDATE ek_LectureDe SET report = ? WHERE lecturede_idx = ?",
        (report, lecturede_idx),
        fetch="none"
    )

    return RedirectResponse("/booking/", status_code=303)


@router.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, user=Depends(get_current_user)):
    """메시지 목록 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    # 대화 상대별 마지막 메시지 조회
    # sender 또는 receiver가 현재 유저인 메시지에서 상대방을 추출
    raw_msgs = execute_query(
        "SELECT M.*, "
        "CASE WHEN M.sender_id = ? THEN M.receiver_id ELSE M.sender_id END AS partner_id "
        "FROM dev_messages M "
        "WHERE M.sender_id = ? OR M.receiver_id = ? "
        "ORDER BY M.sent_at DESC",
        (user["mem_MbrId"], user["mem_MbrId"], user["mem_MbrId"]),
        fetch="all"
    )

    # 대화 상대별 그룹핑
    conversations_map: dict = {}
    for msg in raw_msgs:
        pid = msg["partner_id"]
        if pid not in conversations_map:
            # 강사 정보 조회
            teacher_info = execute_query(
                "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
                "FROM ek_Member WHERE mem_MbrId = ?",
                (pid,),
                fetch="one"
            )
            if not teacher_info:
                continue

            # 안읽은 메시지 수
            unread_row = execute_query(
                "SELECT COUNT(*) AS cnt FROM dev_messages "
                "WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
                (pid, user["mem_MbrId"]),
                fetch="one"
            )
            unread = unread_row["cnt"] if unread_row else 0

            # 시간 표시
            sent = msg["sent_at"]
            now = datetime.now()
            if isinstance(sent, str):
                sent_dt = datetime.strptime(sent, "%Y-%m-%d %H:%M:%S")
            else:
                sent_dt = sent
            if sent_dt.date() == now.date():
                time_label = "오늘"
            elif (now.date() - sent_dt.date()).days == 1:
                time_label = "어제"
            else:
                time_label = f"{sent_dt.month}/{sent_dt.day}"

            conversations_map[pid] = {
                "teacher_id": teacher_info["mem_MbrId"],
                "teacher_name": teacher_info.get("mem_nickname") or teacher_info["mem_MbrName"],
                "teacher_img": teacher_info.get("mem_MbrImg"),
                "last_message": msg["content"],
                "last_time": time_label,
                "unread": unread,
            }

    conversations = list(conversations_map.values())

    # 최신 공지
    latest = execute_query(
        "SELECT board_title AS title, board_Wdate AS created_at FROM ek_Board WHERE board_code = '1' ORDER BY board_Wdate DESC LIMIT 1",
        fetch="one"
    )

    # 전체 안읽은 수
    total_unread = sum(c["unread"] for c in conversations)

    return templates.TemplateResponse(request, "booking/messages.html", {
        "conversations": conversations,
        "latest_notice_date": latest["created_at"][:5].replace("-", "/") if latest else "",
        "latest_notice_title": latest["title"] if latest else "",
        "unread_count": total_unread,
    })


@router.get("/chat/{teacher_id}", response_class=HTMLResponse)
async def chat_page(teacher_id: str, request: Request, user=Depends(get_current_user)):
    """1:1 채팅 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    # 강사 정보
    teacher = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
        "FROM ek_Member WHERE mem_MbrId = ?",
        (teacher_id,),
        fetch="one"
    )
    teacher_name = (teacher.get("mem_nickname") or teacher["mem_MbrName"]) if teacher else ""

    # 메시지 조회
    raw = execute_query(
        "SELECT * FROM dev_messages "
        "WHERE (sender_id = ? AND receiver_id = ?) "
        "   OR (sender_id = ? AND receiver_id = ?) "
        "ORDER BY sent_at ASC",
        (user["mem_MbrId"], teacher_id, teacher_id, user["mem_MbrId"]),
        fetch="all"
    )

    messages = []
    prev_sender = None
    for m in raw:
        is_mine = m["sender_id"] == user["mem_MbrId"]
        sent = m["sent_at"]
        if isinstance(sent, str):
            sent_dt = datetime.strptime(sent, "%Y-%m-%d %H:%M:%S")
        else:
            sent_dt = sent

        show_avatar = (not is_mine) and (m["sender_id"] != prev_sender)
        messages.append({
            "content": m["content"],
            "is_mine": is_mine,
            "time": sent_dt.strftime("%p %I:%M").replace("AM", "오전").replace("PM", "오후"),
            "show_avatar": show_avatar,
        })
        prev_sender = m["sender_id"]

    # 읽음 처리
    execute_query(
        "UPDATE dev_messages SET is_read = 1 "
        "WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (teacher_id, user["mem_MbrId"]),
        fetch="none"
    )

    return templates.TemplateResponse(request, "booking/chat.html", {
        "teacher_id": teacher_id,
        "teacher_name": teacher_name,
        "teacher_field": "AI활용 / Python",
        "messages": messages,
    })


@router.post("/chat/{teacher_id}/send", response_class=HTMLResponse)
async def send_message(teacher_id: str, request: Request,
                       content: str = Form(), user=Depends(get_current_user)):
    """수강생 → 멘토 메시지 전송"""
    if not user:
        return HTMLResponse("", status_code=401)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query(
        "INSERT INTO dev_messages (sender_id, receiver_id, content, sent_at, is_read) "
        "VALUES (?, ?, ?, ?, 0)",
        (user["mem_MbrId"], teacher_id, content, now_str),
        fetch="none"
    )

    # 채팅 페이지로 리다이렉트
    return RedirectResponse(f"/booking/chat/{teacher_id}", status_code=303)


@router.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request, user=Depends(get_current_user)):
    """수강/결제 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    remaining = get_remaining(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])
    total_classes = get_total_classes(user["settle_code"])
    settle_period = get_settle_period(user["settle_code"])

    # 현재 수강권 정보
    settle = execute_query(
        "SELECT S.*, P.package_name, P.week_tcnt, P.lec_time "
        "FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "WHERE S.settle_code = ? AND S.settle_state = 1",
        (user["settle_code"],),
        fetch="one"
    )

    current_plan = None
    if settle:
        sdate = (settle.get("settle_sdate") or "")[:10]
        edate = (settle.get("settle_edate") or "")[:10]
        settle_date = (settle.get("settle_date") or "")[:10]
        current_plan = {
            "package_name": settle["package_name"],
            "lec_time": settle.get("lec_time", 50),
            "settle_date": settle_date,
            "amount": f"{settle.get('settle_amount', 0):,}원",
            "sdate": sdate,
            "edate": edate,
        }

    # 결제 이력 (최근 10건, 슬라이드용)
    history = execute_query(
        "SELECT S.settle_date, S.settle_amount, S.settle_sdate, S.settle_edate, "
        "P.package_name, S.settle_state "
        "FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "WHERE S.settle_mbr_id = ? "
        "ORDER BY S.settle_date DESC LIMIT 20",
        (user["mem_MbrId"],),
        fetch="all"
    )
    payment_history = []
    for h in history:
        sd = (h.get("settle_date") or "")[:10]
        edate = (h.get("settle_edate") or "")[:10]
        # 기간 지났으면 이용종료
        if h["settle_state"] != 1:
            state = "이용종료"
        elif edate and edate < datetime.now().strftime("%Y-%m-%d"):
            state = "이용종료"
        else:
            state = "이용중"
        payment_history.append({
            "package_name": h["package_name"],
            "date": sd,
            "amount": f"{h['settle_amount']:,}원",
            "sdate": (h.get("settle_sdate") or "")[:10],
            "edate": (h.get("settle_edate") or "")[:10],
            "state": state,
        })

    return templates.TemplateResponse(request, "booking/payment.html", {
        "current_plan": current_plan,
        "remaining": remaining,
        "monthly": monthly,
        "total_classes": total_classes,
        "settle_period": settle_period,
        "payment_history": payment_history,
    })


@router.get("/notices", response_class=HTMLResponse)
async def notices_page(request: Request, user=Depends(get_current_user)):
    """공지사항 목록 페이지 (ek_Board board_code=1)"""
    if not user:
        return RedirectResponse("/booking/")

    notices_raw = execute_query(
        "SELECT board_idx, board_title, board_content, board_Wdate, board_open_state "
        "FROM ek_Board WHERE board_code = '1' "
        "ORDER BY board_Wdate DESC LIMIT 30",
        fetch="all"
    )
    notices = []
    for n in notices_raw:
        date = (n.get("board_Wdate") or "")[:10]
        content = n.get("board_content") or ""
        summary = content[:50].replace("\n", " ") + ("..." if len(content) > 50 else "")
        notices.append({
            "notice_id": n["board_idx"],
            "title": n.get("board_title") or "",
            "summary": summary,
            "date": date,
        })

    return templates.TemplateResponse(request, "booking/notices.html", {
        "notices": notices,
    })


@router.get("/notices/{notice_id}", response_class=HTMLResponse)
async def notice_detail_page(notice_id: int, request: Request, user=Depends(get_current_user)):
    """공지사항 상세 페이지 (ek_Board)"""
    if not user:
        return RedirectResponse("/booking/")

    notice = execute_query(
        "SELECT board_idx AS notice_id, board_title AS title, "
        "board_content AS content, board_Wdate AS date "
        "FROM ek_Board WHERE board_idx = ?",
        (notice_id,),
        fetch="one"
    )

    return templates.TemplateResponse(request, "booking/notice_detail.html", {
        "notice": notice,
    })


@router.get("/mypage", response_class=HTMLResponse)
async def mypage(request: Request, user=Depends(get_current_user)):
    """MY 페이지"""
    if not user:
        return RedirectResponse("/booking/")

    remaining = get_remaining(user["settle_code"])
    monthly = is_monthly_plan(user["settle_code"])
    total_classes = get_total_classes(user["settle_code"])

    # 완료된 수업 수 (실제 예약 테이블에서)
    completed_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM ek_Sch_Detail_Room_mem "
        "WHERE mem_mbrid = ? AND status = 1 "
        "AND datetime(l_s_date, '+9 hours') < datetime('now', '+9 hours')",
        (user["mem_MbrId"],),
        fetch="one"
    )
    completed = completed_row["cnt"] if completed_row else 0

    # 개인정보 조회
    member_info = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_TelNo2, mem_TelNo3, "
        "mem_MbrType, mem_edate FROM ek_Member WHERE mem_MbrId = ?",
        (user["mem_MbrId"],),
        fetch="one"
    )

    return templates.TemplateResponse(request, "booking/mypage.html", {
        "user": user,
        "remaining": remaining,
        "monthly": monthly,
        "total_classes": total_classes,
        "stats": {"completed": completed},
        "member": member_info,
    })
