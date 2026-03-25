# app/routers/teacher_pages.py
# 강사 포털 웹 라우터
# Jinja2 SSR + HTMX partial 렌더링
# URL 패턴: /teacher/*

from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user
from app.database import execute_query

router = APIRouter(prefix="/teacher", tags=["강사 포털"])
templates = Jinja2Templates(directory="templates")

DAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


async def _require_teacher(request: Request):
    """강사 인증 헬퍼. 강사가 아니면 None 반환."""
    user = await get_current_user(request)
    if not user or user.get("role") != "teacher":
        return None
    return user


# ===== 페이지 라우트 =====


@router.get("/", response_class=HTMLResponse)
async def teacher_home(request: Request):
    """강사 홈 - 오늘 수업 목록"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]
    today = datetime.now().strftime("%Y-%m-%d")

    # 오늘 수업 조회
    today_classes = execute_query(
        "SELECT R.idx, R.sch_room_idx, R.mem_mbrid, datetime(R.l_s_date, '+9 hours') AS l_s_date, datetime(R.l_f_date, '+9 hours') AS l_f_date, R.status, "
        "M.mem_MbrName AS student_name "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Member M ON R.mem_mbrid = M.mem_MbrId "
        "JOIN ek_Sch_Detail_Room S ON R.sch_room_idx = S.sch_room_idx "
        "WHERE S.sch_teach_id = ? AND date(R.l_s_date, '+9 hours') = ? AND R.status = 1 "
        "ORDER BY R.l_s_date",
        (teacher_id, today),
        fetch="all"
    )

    now = datetime.now()
    classes = []
    for c in today_classes:
        s_dt = datetime.strptime(c["l_s_date"], "%Y-%m-%d %H:%M:%S")
        e_dt = datetime.strptime(c["l_f_date"], "%Y-%m-%d %H:%M:%S")
        is_done = now > e_dt

        # 메모 존재 여부 확인
        memo = execute_query(
            "SELECT memo_id FROM dev_class_memos "
            "WHERE teacher_id = ? AND student_id = ? AND lesson_date = ?",
            (teacher_id, c["mem_mbrid"], today),
            fetch="one"
        )

        classes.append({
            "idx": c["idx"],
            "student_id": c["mem_mbrid"],
            "student_name": c["student_name"],
            "start_time": s_dt.strftime("%H:%M"),
            "end_time": e_dt.strftime("%H:%M"),
            "is_done": is_done,
            "has_memo": memo is not None,
        })

    # 안읽은 메시지 수
    unread_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM dev_messages "
        "WHERE receiver_id = ? AND is_read = 0",
        (teacher_id,),
        fetch="one"
    )
    unread_count = unread_row["cnt"] if unread_row else 0

    return templates.TemplateResponse(request, "teacher/home.html", {
        "user": user,
        "today": today,
        "today_display": now.strftime("%m월 %d일") + f" {DAYS_KO[now.weekday()]}요일",
        "classes": classes,
        "class_count": len(classes),
        "unread_count": unread_count,
        "active_tab": "home",
    })


@router.get("/schedule", response_class=HTMLResponse)
async def teacher_schedule(request: Request, week: int = 0):
    """강사 주간 스케줄"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]
    now = datetime.now()

    # 주 시작일 (월요일 기준)
    start_of_week = now - timedelta(days=now.weekday()) + timedelta(weeks=week)
    end_of_week = start_of_week + timedelta(days=6)

    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = end_of_week.strftime("%Y-%m-%d")

    # 해당 주 슬롯 조회
    slots = execute_query(
        "SELECT S.sch_room_idx, datetime(S.sch_detail_Stime, '+9 hours') AS sch_detail_Stime, datetime(S.sch_detail_Etime, '+9 hours') AS sch_detail_Etime, S.sch_room_status "
        "FROM ek_Sch_Detail_Room S "
        "WHERE S.sch_teach_id = ? AND S.sch_room_status = 1 "
        "AND date(S.sch_detail_Stime, '+9 hours') BETWEEN ? AND ? "
        "ORDER BY S.sch_detail_Stime",
        (teacher_id, start_str, end_str),
        fetch="all"
    )

    # 예약 정보 조회
    bookings = execute_query(
        "SELECT R.sch_room_idx, R.mem_mbrid, M.mem_MbrName AS student_name "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Member M ON R.mem_mbrid = M.mem_MbrId "
        "WHERE R.status = 1 AND R.sch_room_idx IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room "
        "  WHERE sch_teach_id = ? AND date(sch_detail_Stime) BETWEEN ? AND ?"
        ")",
        (teacher_id, start_str, end_str),
        fetch="all"
    )
    booking_map = {b["sch_room_idx"]: b for b in bookings}

    # 일별 그룹핑
    days = []
    for d in range(7):
        day_date = start_of_week + timedelta(days=d)
        day_str = day_date.strftime("%Y-%m-%d")
        day_slots = []
        for s in slots:
            slot_date = s["sch_detail_Stime"][:10]
            if slot_date == day_str:
                s_dt = datetime.strptime(s["sch_detail_Stime"], "%Y-%m-%d %H:%M:%S")
                e_dt = datetime.strptime(s["sch_detail_Etime"], "%Y-%m-%d %H:%M:%S")
                booking = booking_map.get(s["sch_room_idx"])
                day_slots.append({
                    "room_idx": s["sch_room_idx"],
                    "start_time": s_dt.strftime("%H:%M"),
                    "end_time": e_dt.strftime("%H:%M"),
                    "booked": booking is not None,
                    "student_name": booking["student_name"] if booking else None,
                })
        if d < 5:  # 월~금만 표시 (주말에 슬롯 없으면)
            days.append({
                "date": day_str,
                "label": f"{day_date.month}/{day_date.day} {DAYS_KO[day_date.weekday()]}요일",
                "weekday": DAYS_KO[day_date.weekday()],
                "slots": day_slots,
                "is_today": day_str == now.strftime("%Y-%m-%d"),
            })

    # 안읽은 메시지 수
    unread_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM dev_messages "
        "WHERE receiver_id = ? AND is_read = 0",
        (teacher_id,),
        fetch="one"
    )
    unread_count = unread_row["cnt"] if unread_row else 0

    week_label = "이번 주" if week == 0 else ("다음 주" if week == 1 else f"{week}주 후")
    today = datetime.now().strftime("%Y-%m-%d")

    return templates.TemplateResponse(request, "teacher/schedule.html", {
        "user": user,
        "days": days,
        "week": week,
        "week_label": week_label,
        "today": today,
        "unread_count": unread_count,
        "active_tab": "schedule",
    })


# ===== 수업 슬롯 관리 =====


@router.post("/schedule/add", response_class=HTMLResponse)
async def add_slot(
    request: Request,
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    repeat_weeks: int = Form(1),
):
    """수업 가능 시간 추가 (반복 포함)"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]
    base_date = datetime.strptime(date, "%Y-%m-%d")
    added = 0

    for w in range(repeat_weeks):
        slot_date = base_date + timedelta(weeks=w)
        slot_date_str = slot_date.strftime("%Y-%m-%d")
        s_time = f"{slot_date_str} {start_time}:00"
        e_time = f"{slot_date_str} {end_time}:00"

        # 중복 체크
        existing = execute_query(
            "SELECT sch_room_idx FROM ek_Sch_Detail_Room "
            "WHERE sch_teach_id = ? AND sch_detail_Stime = ?",
            (teacher_id, s_time),
            fetch="one"
        )
        if existing:
            continue

        execute_query(
            "INSERT INTO ek_Sch_Detail_Room (sch_teach_id, sch_detail_Stime, sch_detail_Etime, sch_room_status, edc_idx) "
            "VALUES (?, ?, ?, 1, 1)",
            (teacher_id, s_time, e_time),
            fetch="none"
        )
        added += 1

    # 추가한 주로 리다이렉트
    return RedirectResponse(f"/teacher/schedule?week=0&added={added}", status_code=303)


@router.post("/schedule/delete/{room_idx}", response_class=HTMLResponse)
async def delete_slot(room_idx: int, request: Request):
    """수업 슬롯 삭제 (예약 없는 경우만)"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    # 내 슬롯인지 확인
    slot = execute_query(
        "SELECT sch_room_idx FROM ek_Sch_Detail_Room "
        "WHERE sch_room_idx = ? AND sch_teach_id = ?",
        (room_idx, teacher_id),
        fetch="one"
    )
    if not slot:
        return RedirectResponse("/teacher/schedule", status_code=303)

    # 예약이 있는지 확인
    booking = execute_query(
        "SELECT idx FROM ek_Sch_Detail_Room_mem "
        "WHERE sch_room_idx = ? AND status = 1",
        (room_idx,),
        fetch="one"
    )
    if booking:
        # 예약이 있으면 삭제 불가
        return RedirectResponse("/teacher/schedule?error=booked", status_code=303)

    # 삭제
    execute_query(
        "DELETE FROM ek_Sch_Detail_Room WHERE sch_room_idx = ?",
        (room_idx,),
        fetch="none"
    )

    return RedirectResponse("/teacher/schedule", status_code=303)


@router.get("/students", response_class=HTMLResponse)
async def teacher_students(request: Request):
    """내 수강생 목록"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    # 이 강사에게 예약한 적 있는 수강생 조회
    students = execute_query(
        "SELECT DISTINCT M.mem_MbrId, M.mem_MbrName, M.mem_nickname, "
        "P.package_name, "
        "(SELECT MAX(R2.l_s_date) FROM ek_Sch_Detail_Room_mem R2 "
        " JOIN ek_Sch_Detail_Room S2 ON R2.sch_room_idx = S2.sch_room_idx "
        " WHERE S2.sch_teach_id = ? AND R2.mem_mbrid = M.mem_MbrId AND R2.status = 1"
        ") AS last_lesson, "
        "(P.class_cnt - COALESCE("
        "  (SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem R3 "
        "   WHERE R3.mem_mbrid = M.mem_MbrId AND R3.settle_code = ST.settle_code AND R3.status = 1"
        "  ), 0)) AS remaining "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room S ON R.sch_room_idx = S.sch_room_idx "
        "JOIN ek_Member M ON R.mem_mbrid = M.mem_MbrId "
        "JOIN ek_Settlement ST ON R.settle_code = ST.settle_code "
        "JOIN ek_Package P ON ST.settle_package_code = P.package_code "
        "WHERE S.sch_teach_id = ? AND R.status = 1 "
        "GROUP BY M.mem_MbrId "
        "ORDER BY M.mem_MbrName",
        (teacher_id, teacher_id),
        fetch="all"
    )

    student_list = []
    for s in students:
        last = s.get("last_lesson")
        if last and isinstance(last, str) and len(last) >= 10:
            last_dt = datetime.strptime(last[:10], "%Y-%m-%d")
            last_display = f"{last_dt.month}/{last_dt.day}"
        else:
            last_display = "-"

        student_list.append({
            "id": s["mem_MbrId"],
            "name": s.get("mem_nickname") or s["mem_MbrName"],
            "package": s.get("package_name", ""),
            "remaining": s.get("remaining", 0),
            "last_lesson": last_display,
        })

    # 안읽은 메시지 수
    unread_row = execute_query(
        "SELECT COUNT(*) AS cnt FROM dev_messages "
        "WHERE receiver_id = ? AND is_read = 0",
        (teacher_id,),
        fetch="one"
    )
    unread_count = unread_row["cnt"] if unread_row else 0

    return templates.TemplateResponse(request, "teacher/students.html", {
        "user": user,
        "students": student_list,
        "unread_count": unread_count,
        "active_tab": "students",
    })


@router.get("/messages", response_class=HTMLResponse)
async def teacher_messages(request: Request):
    """강사 메시지 목록"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    # 대화 상대별 마지막 메시지 조회
    raw_msgs = execute_query(
        "SELECT M.*, "
        "CASE WHEN M.sender_id = ? THEN M.receiver_id ELSE M.sender_id END AS partner_id "
        "FROM dev_messages M "
        "WHERE M.sender_id = ? OR M.receiver_id = ? "
        "ORDER BY M.sent_at DESC",
        (teacher_id, teacher_id, teacher_id),
        fetch="all"
    )

    conversations_map: dict = {}
    for msg in raw_msgs:
        pid = msg["partner_id"]
        if pid not in conversations_map:
            student_info = execute_query(
                "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
                "FROM ek_Member WHERE mem_MbrId = ?",
                (pid,),
                fetch="one"
            )
            if not student_info:
                continue

            unread_row = execute_query(
                "SELECT COUNT(*) AS cnt FROM dev_messages "
                "WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
                (pid, teacher_id),
                fetch="one"
            )
            unread = unread_row["cnt"] if unread_row else 0

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
                "student_id": student_info["mem_MbrId"],
                "student_name": student_info.get("mem_nickname") or student_info["mem_MbrName"],
                "student_img": student_info.get("mem_MbrImg"),
                "last_message": msg["content"],
                "last_time": time_label,
                "unread": unread,
            }

    conversations = list(conversations_map.values())
    total_unread = sum(c["unread"] for c in conversations)

    return templates.TemplateResponse(request, "teacher/messages.html", {
        "user": user,
        "conversations": conversations,
        "unread_count": total_unread,
        "active_tab": "messages",
    })


@router.get("/chat/{student_id}", response_class=HTMLResponse)
async def teacher_chat(student_id: str, request: Request):
    """강사 1:1 채팅"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    # 수강생 정보
    student = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
        "FROM ek_Member WHERE mem_MbrId = ?",
        (student_id,),
        fetch="one"
    )
    student_name = (student.get("mem_nickname") or student["mem_MbrName"]) if student else ""

    # 메시지 조회
    raw = execute_query(
        "SELECT * FROM dev_messages "
        "WHERE (sender_id = ? AND receiver_id = ?) "
        "   OR (sender_id = ? AND receiver_id = ?) "
        "ORDER BY sent_at ASC",
        (teacher_id, student_id, student_id, teacher_id),
        fetch="all"
    )

    messages = []
    prev_sender = None
    for m in raw:
        is_mine = m["sender_id"] == teacher_id
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
        (student_id, teacher_id),
        fetch="none"
    )

    return templates.TemplateResponse(request, "teacher/chat.html", {
        "user": user,
        "student_id": student_id,
        "student_name": student_name,
        "messages": messages,
    })


@router.post("/chat/{student_id}/send", response_class=HTMLResponse)
async def teacher_chat_send(student_id: str, request: Request, content: str = Form(...)):
    """강사 메시지 전송"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute_query(
        "INSERT INTO dev_messages (sender_id, receiver_id, content, sent_at, is_read) "
        "VALUES (?, ?, ?, ?, 0)",
        (teacher_id, student_id, content, now_str),
        fetch="none"
    )

    # 채팅 영역 전체 다시 렌더링 (HTMX partial)
    raw = execute_query(
        "SELECT * FROM dev_messages "
        "WHERE (sender_id = ? AND receiver_id = ?) "
        "   OR (sender_id = ? AND receiver_id = ?) "
        "ORDER BY sent_at ASC",
        (teacher_id, student_id, student_id, teacher_id),
        fetch="all"
    )

    student = execute_query(
        "SELECT mem_MbrName, mem_nickname FROM ek_Member WHERE mem_MbrId = ?",
        (student_id,),
        fetch="one"
    )
    student_name = (student.get("mem_nickname") or student["mem_MbrName"]) if student else ""

    messages = []
    prev_sender = None
    for m in raw:
        is_mine = m["sender_id"] == teacher_id
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

    return templates.TemplateResponse(request, "teacher/partials/chat_messages.html", {
        "messages": messages,
        "student_name": student_name,
    })


@router.post("/memo", response_class=HTMLResponse)
async def save_memo(
    request: Request,
    student_id: str = Form(...),
    lesson_date: str = Form(...),
    content: str = Form(...),
):
    """수업 메모 저장"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    # 기존 메모 확인 (같은 날 같은 학생)
    existing = execute_query(
        "SELECT memo_id FROM dev_class_memos "
        "WHERE teacher_id = ? AND student_id = ? AND lesson_date = ?",
        (teacher_id, student_id, lesson_date),
        fetch="one"
    )

    if existing:
        execute_query(
            "UPDATE dev_class_memos SET content = ? WHERE memo_id = ?",
            (content, existing["memo_id"]),
            fetch="none"
        )
    else:
        execute_query(
            "INSERT INTO dev_class_memos (teacher_id, student_id, lesson_date, content) "
            "VALUES (?, ?, ?, ?)",
            (teacher_id, student_id, lesson_date, content),
            fetch="none"
        )

    # 토스트 응답 (HTMX)
    return HTMLResponse(
        '<div hx-swap-oob="innerHTML:#memo-toast">'
        '<div x-data="{ show: true }" x-show="show" x-init="setTimeout(() => show = false, 2200)" '
        'class="fixed bottom-24 left-1/2 -translate-x-1/2 bg-g-800 text-white px-5 py-2.5 rounded-xl text-[13px] font-medium shadow-lg z-[999]">'
        '메모가 저장되었습니다</div></div>'
    )


@router.get("/memo/{student_id}/{lesson_date}", response_class=HTMLResponse)
async def get_memo(student_id: str, lesson_date: str, request: Request):
    """수업 메모 조회 (HTMX modal 용)"""
    user = await _require_teacher(request)
    if not user:
        return RedirectResponse("/booking/")

    teacher_id = user["mem_MbrId"]

    memo = execute_query(
        "SELECT content FROM dev_class_memos "
        "WHERE teacher_id = ? AND student_id = ? AND lesson_date = ?",
        (teacher_id, student_id, lesson_date),
        fetch="one"
    )

    student = execute_query(
        "SELECT mem_MbrName, mem_nickname FROM ek_Member WHERE mem_MbrId = ?",
        (student_id,),
        fetch="one"
    )
    student_name = (student.get("mem_nickname") or student["mem_MbrName"]) if student else ""

    return templates.TemplateResponse(request, "teacher/partials/memo_modal.html", {
        "student_id": student_id,
        "student_name": student_name,
        "lesson_date": lesson_date,
        "memo_content": memo["content"] if memo else "",
    })
