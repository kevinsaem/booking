# app/routers/booking_pages.py
# 수강생 웹 라우터
# Jinja2 SSR + HTMX partial 렌더링
# URL 패턴: /booking/*

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user, login, create_jwt
from app.services.schedule_service import (
    get_available_dates, get_time_slots, get_available_teachers,
    get_calendar_cells, get_repeat_weeks
)
from app.services.booking_service import (
    get_remaining, create_booking, get_my_bookings, cancel_booking
)

router = APIRouter(prefix="/booking", tags=["수강생 웹"])
templates = Jinja2Templates(directory="templates/booking")
partials = Jinja2Templates(directory="templates/partials")

# ===== 페이지 라우트 =====

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, user=Depends(get_current_user)):
    """홈 페이지"""
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    
    remaining = get_remaining(user["settle_code"])
    next_booking = get_my_bookings(user["mem_MbrId"], limit=1, upcoming=True)
    
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "remaining": remaining,
        "next_booking": next_booking[0] if next_booking else None,
        "unread_count": 1,  # TODO: 실제 안읽은 메시지 수 조회
        "latest_notice": {"title": "4월 AI활용 특강 안내", "summary": "ChatGPT, Claude 실전 활용법"}
    })

@router.post("/login", response_class=HTMLResponse)
async def do_login(request: Request, name: str = Form(), code: str = Form()):
    """로그인 처리"""
    user = login(name, code)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "이름 또는 인증번호가 일치하지 않습니다."
        })
    
    response = RedirectResponse("/booking/", status_code=303)
    token = create_jwt(user)
    response.set_cookie("token", token, httponly=True, samesite="lax", max_age=1800)
    return response

@router.post("/logout")
async def do_logout():
    """로그아웃"""
    response = RedirectResponse("/booking/", status_code=303)
    response.delete_cookie("token")
    return response

@router.get("/calendar", response_class=HTMLResponse)
async def booking_page(request: Request, user=Depends(get_current_user),
                       year: int = 2026, month: int = 4):
    """수업 예약 페이지 (캘린더)"""
    remaining = get_remaining(user["settle_code"])
    available_dates = get_available_dates(year, month)
    calendar_cells = get_calendar_cells(year, month, available_dates)
    
    return templates.TemplateResponse("booking.html", {
        "request": request,
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
    remaining = get_remaining(user["settle_code"])
    repeat_weeks = get_repeat_weeks(date, time, room_idx, teacher_id)
    
    return templates.TemplateResponse("repeat.html", {
        "request": request,
        "remaining": remaining,
        "repeat_weeks": repeat_weeks,
        "base_date": date,
        "time": time,
        "room_idx": room_idx,
        "teacher_id": teacher_id,
    })

@router.post("/confirm", response_class=HTMLResponse)
async def confirm_page(request: Request, user=Depends(get_current_user)):
    """예약 확인 페이지"""
    form = await request.form()
    dates = form.getlist("dates[]")
    remaining = get_remaining(user["settle_code"])
    
    return templates.TemplateResponse("confirm.html", {
        "request": request,
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
    form = await request.form()
    dates = form.getlist("dates[]")
    room_idx = int(form.get("room_idx"))
    teacher_id = form.get("teacher_id")
    settle_code = int(form.get("settle_code"))
    
    # 예약 INSERT (서비스 레이어에서 트랜잭션 처리)
    result = create_booking(
        room_idx=room_idx,
        mem_id=user["mem_MbrId"],
        settle_code=settle_code,
        dates=dates
    )
    
    remaining = get_remaining(settle_code)
    
    # TODO: 카카오 알림톡 발송 (BackgroundTasks)
    
    return templates.TemplateResponse("complete.html", {
        "request": request,
        "teacher_name": form.get("teacher_name", ""),
        "booking_count": len(dates),
        "remaining": remaining,
    })

@router.get("/my-bookings", response_class=HTMLResponse)
async def my_bookings_page(request: Request, user=Depends(get_current_user)):
    """내 예약 페이지"""
    remaining = get_remaining(user["settle_code"])
    bookings = get_my_bookings(user["mem_MbrId"])
    
    return templates.TemplateResponse("my_bookings.html", {
        "request": request,
        "remaining": remaining,
        "bookings": bookings,
    })

@router.post("/cancel/{idx}", response_class=HTMLResponse)
async def cancel_booking_action(idx: int, request: Request, user=Depends(get_current_user)):
    """예약 취소 (HTMX partial 반환)"""
    result = cancel_booking(idx, user["mem_MbrId"])
    # 취소된 예약 행을 반환 (HTMX swap)
    booking = get_my_bookings(user["mem_MbrId"], booking_idx=idx)
    return partials.TemplateResponse("booking_row_cancelled.html", {
        "request": request,
        "booking": booking
    })

# ===== HTMX Partial 라우트 =====

@router.get("/partials/calendar-grid", response_class=HTMLResponse)
async def calendar_grid_partial(request: Request, year: int, month: int,
                                user=Depends(get_current_user)):
    """캘린더 그리드 부분 렌더링"""
    available_dates = get_available_dates(year, month)
    calendar_cells = get_calendar_cells(year, month, available_dates)
    return partials.TemplateResponse("calendar_grid.html", {
        "request": request,
        "calendar_cells": calendar_cells,
    })

@router.get("/partials/time-slots", response_class=HTMLResponse)
async def time_slots_partial(request: Request, date: str, user=Depends(get_current_user)):
    """시간 슬롯 부분 렌더링"""
    slots = get_time_slots(date)
    return partials.TemplateResponse("time_slots.html", {
        "request": request,
        "time_slots": slots,
        "selected_date_label": date,
    })

@router.get("/partials/teacher-list", response_class=HTMLResponse)
async def teacher_list_partial(request: Request, date: str, time: str,
                               room_idx: int, user=Depends(get_current_user)):
    """강사 목록 부분 렌더링"""
    teachers = get_available_teachers(date, time, room_idx)
    return partials.TemplateResponse("teacher_list.html", {
        "request": request,
        "teachers": teachers,
    })

@router.get("/partials/my-bookings-summary", response_class=HTMLResponse)
async def my_bookings_summary_partial(request: Request, user=Depends(get_current_user)):
    """홈 화면 예약 요약 부분 렌더링"""
    bookings = get_my_bookings(user["mem_MbrId"], limit=2, upcoming=True)
    return partials.TemplateResponse("my_bookings_summary.html", {
        "request": request,
        "bookings": bookings,
    })

# ===== 추가 페이지 (학습, 메시지, 결제, 공지, MY) =====

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user=Depends(get_current_user)):
    """학습 현황 페이지"""
    # TODO: 실제 학습 데이터 조회
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "stats": {"completed": 13, "remaining": 7, "attendance_rate": 92, "progress": 65},
        "package": {"name": "AI활용 실무 과정", "total_count": 20},
        "recent_lessons": [
            {"topic": "ChatGPT API 활용", "date": "3/19", "teacher_name": "김코딩", "status": "present"},
            {"topic": "Python 데이터 분석", "date": "3/17", "teacher_name": "박데이터", "status": "present"},
            {"topic": "AI 이미지 생성", "date": "3/14", "teacher_name": "김코딩", "status": "present"},
        ],
    })

@router.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request, user=Depends(get_current_user)):
    """메시지 목록 페이지"""
    # TODO: 실제 대화 목록 조회
    return templates.TemplateResponse("messages.html", {
        "request": request,
        "conversations": [
            {"teacher_id": "T001", "teacher_name": "김코딩", "teacher_img": None,
             "last_message": "다음 수업 때 프롬프트 엔지니어링을 다룰 예정입니다.", "last_time": "오늘", "unread": 1},
            {"teacher_id": "T002", "teacher_name": "박데이터", "teacher_img": None,
             "last_message": "과제 확인했습니다. 잘 하셨어요!", "last_time": "어제", "unread": 0},
        ],
        "latest_notice_date": "3/18",
        "latest_notice_title": "4월 특강 신청이 시작되었습니다.",
        "unread_count": 1,
    })

@router.get("/chat/{teacher_id}", response_class=HTMLResponse)
async def chat_page(teacher_id: str, request: Request, user=Depends(get_current_user)):
    """1:1 채팅 페이지"""
    # TODO: 실제 메시지 조회
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "teacher_id": teacher_id,
        "teacher_name": "김코딩",
        "teacher_field": "AI활용 / Python",
        "messages": [
            {"content": "선생님 다음 수업은 어떤 내용인가요?", "is_mine": True, "time": "오후 2:30", "show_avatar": False},
            {"content": "다음 수업에서는 ChatGPT API를 활용한 프롬프트 엔지니어링을 다룰 예정입니다.", "is_mine": False, "time": "오후 2:35", "show_avatar": True},
            {"content": "준비물이 있을까요?", "is_mine": True, "time": "오후 2:36", "show_avatar": False},
            {"content": "OpenAI API 키만 준비해주시면 됩니다. 수업 전에 발급 방법도 안내드릴게요!", "is_mine": False, "time": "오후 2:40", "show_avatar": True},
        ],
    })

@router.get("/payment", response_class=HTMLResponse)
async def payment_page(request: Request, user=Depends(get_current_user)):
    """수강/결제 페이지"""
    # TODO: 실제 결제 데이터 조회
    return templates.TemplateResponse("payment.html", {
        "request": request,
        "current_plan": {
            "package_name": "AI활용 실무 과정",
            "description": "진로반 주2회 · 20회 패키지",
            "settle_date": "2026.03.01",
            "amount": "290,000",
            "period": "03.01 ~ 04.30",
            "remaining": 7,
        },
        "packages": [
            {"name": "취미반 주2회", "price": "210,000", "description": "94.5분/회 · 주2회 4주 · 총 756분", "is_best": False},
            {"name": "진로반 주2회", "price": "290,000", "description": "157.5분/회 · 주2회 4주 · 총 1,260분", "is_best": False},
            {"name": "월정기 진로반", "price": "450,000", "description": "157.5분/회 · 주5회 · 총 3,150분", "is_best": True},
        ],
        "payment_history": [
            {"package_name": "진로반 주2회", "date": "2026.03.01", "amount": "290,000"},
        ],
    })

@router.get("/notice", response_class=HTMLResponse)
async def notice_page(request: Request, user=Depends(get_current_user)):
    """공지사항 페이지"""
    # TODO: 실제 공지 조회
    return templates.TemplateResponse("notice.html", {
        "request": request,
        "notices": [
            {"title": "4월 AI활용 특강 안내", "date": "2026.03.20", "type": "notice", "is_new": True,
             "summary": "ChatGPT, Midjourney, Claude를 활용한 실전 AI 활용법을 배우는 특강이 4월에 진행됩니다."},
            {"title": "설 연휴 휴원 안내", "date": "2026.03.15", "type": "notice", "is_new": False,
             "summary": "2/7(금)~2/11(화) 설 연휴 기간 휴원합니다."},
            {"title": "친구 추천 이벤트 - 1회 무료!", "date": "2026.03.10", "type": "event", "is_new": False,
             "summary": "성인반 친구를 추천하시면 추천인과 피추천인 모두 1회 무료 수업을 드립니다."},
        ],
    })

@router.get("/mypage", response_class=HTMLResponse)
async def mypage(request: Request, user=Depends(get_current_user)):
    """MY 페이지"""
    remaining = get_remaining(user["settle_code"])
    return templates.TemplateResponse("mypage.html", {
        "request": request,
        "user": user,
        "remaining": remaining,
        "stats": {"completed": 13, "attendance_rate": 92},
    })
