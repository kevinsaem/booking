# app/routers/message.py
# 메시지 시스템 라우터
# 수강생: 메시지함, 대화, 메시지 보내기
# 멘토: 토큰 기반 답변 (로그인 불필요)

import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user
from app.services.email_service import (
    send_email,
    build_mentor_notification_email,
    build_student_notification_email,
)
from app.database import execute_query
from app.config import settings

router = APIRouter(prefix="/message", tags=["메시지"])
templates = Jinja2Templates(directory="templates")

# 토큰 유효기간 (48시간)
TOKEN_EXPIRE_HOURS = 48


def _get_base_url(request: Request) -> str:
    """요청에서 base URL 추출"""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme}://{host}"


def _format_time_label(sent_str: str) -> str:
    """시간 표시 포맷: 오늘/어제/M/D"""
    now = datetime.now()
    try:
        sent_dt = datetime.strptime(sent_str[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ""
    if sent_dt.date() == now.date():
        return "오늘"
    elif (now.date() - sent_dt.date()).days == 1:
        return "어제"
    else:
        return f"{sent_dt.month}/{sent_dt.day}"


def _format_chat_time(sent_str: str) -> str:
    """채팅 시간 표시: 오전/오후 HH:MM"""
    try:
        sent_dt = datetime.strptime(sent_str[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ""
    return sent_dt.strftime("%p %I:%M").replace("AM", "오전").replace("PM", "오후")


# ===== 수강생 기능 =====


@router.get("/", response_class=HTMLResponse)
async def message_list(request: Request, user=Depends(get_current_user)):
    """메시지함: 대화 목록"""
    if not user:
        return RedirectResponse("/booking/")

    my_id = user["mem_MbrId"]

    # 대화 상대별 마지막 메시지 조회
    raw_msgs = execute_query(
        "SELECT M.msg_idx, M.sender_id, M.receiver_id, M.content, M.created_at, M.is_read, "
        "CASE WHEN M.sender_id = ? THEN M.receiver_id ELSE M.sender_id END AS partner_id "
        "FROM ek_message M "
        "WHERE M.sender_id = ? OR M.receiver_id = ? "
        "ORDER BY M.created_at DESC",
        (my_id, my_id, my_id),
        fetch="all"
    )

    # 대화 상대별 그룹핑 (최신 메시지 기준)
    conversations_map: dict = {}
    for msg in raw_msgs:
        pid = msg["partner_id"]
        if pid in conversations_map:
            continue

        # 상대방 정보 조회
        partner_info = execute_query(
            "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
            "FROM ek_Member WHERE mem_MbrId = ?",
            (pid,),
            fetch="one"
        )
        if not partner_info:
            continue

        # 안읽은 메시지 수
        unread_row = execute_query(
            "SELECT COUNT(*) AS cnt FROM ek_message "
            "WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
            (pid, my_id),
            fetch="one"
        )
        unread = unread_row["cnt"] if unread_row else 0

        conversations_map[pid] = {
            "teacher_id": partner_info["mem_MbrId"],
            "teacher_name": partner_info.get("mem_nickname") or partner_info["mem_MbrName"],
            "teacher_img": partner_info.get("mem_MbrImg"),
            "last_message": msg["content"][:50] if msg["content"] else "",
            "last_time": _format_time_label(msg.get("created_at", "")),
            "unread": unread,
        }

    conversations = list(conversations_map.values())

    # 최신 공지
    latest = execute_query(
        "SELECT board_title AS title, board_Wdate AS created_at "
        "FROM ek_Board WHERE board_code = '1' ORDER BY board_Wdate DESC LIMIT 1",
        fetch="one"
    )

    total_unread = sum(c["unread"] for c in conversations)

    return templates.TemplateResponse(request, "booking/messages.html", {
        "conversations": conversations,
        "latest_notice_date": latest["created_at"][:5].replace("-", "/") if latest else "",
        "latest_notice_title": latest["title"] if latest else "",
        "unread_count": total_unread,
    })


@router.get("/chat/{mentor_id}", response_class=HTMLResponse)
async def chat_page(mentor_id: str, request: Request, user=Depends(get_current_user)):
    """특정 멘토와의 대화 화면"""
    if not user:
        return RedirectResponse("/booking/")

    my_id = user["mem_MbrId"]

    # 멘토 정보
    mentor = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
        "FROM ek_Member WHERE mem_MbrId = ?",
        (mentor_id,),
        fetch="one"
    )
    mentor_name = (mentor.get("mem_nickname") or mentor["mem_MbrName"]) if mentor else ""

    # 메시지 조회 (시간순)
    raw = execute_query(
        "SELECT msg_idx, sender_id, receiver_id, content, created_at, is_read "
        "FROM ek_message "
        "WHERE (sender_id = ? AND receiver_id = ?) "
        "   OR (sender_id = ? AND receiver_id = ?) "
        "ORDER BY created_at ASC",
        (my_id, mentor_id, mentor_id, my_id),
        fetch="all"
    )

    messages = []
    prev_sender = None
    for m in raw:
        is_mine = m["sender_id"] == my_id
        show_avatar = (not is_mine) and (m["sender_id"] != prev_sender)
        messages.append({
            "content": m["content"],
            "is_mine": is_mine,
            "time": _format_chat_time(m.get("created_at", "")),
            "show_avatar": show_avatar,
        })
        prev_sender = m["sender_id"]

    # 읽음 처리
    execute_query(
        "UPDATE ek_message SET is_read = 1 "
        "WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (mentor_id, my_id),
        fetch="none"
    )

    return templates.TemplateResponse(request, "booking/chat.html", {
        "teacher_id": mentor_id,
        "teacher_name": mentor_name,
        "teacher_field": "",
        "messages": messages,
    })


@router.post("/send", response_class=HTMLResponse)
async def send_message(
    request: Request,
    background_tasks: BackgroundTasks,
    mentor_id: str = Form(),
    content: str = Form(),
    user=Depends(get_current_user),
):
    """수강생 → 멘토 메시지 보내기 + 이메일 알림"""
    if not user:
        return HTMLResponse("", status_code=401)

    my_id = user["mem_MbrId"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 메시지 저장
    execute_query(
        "INSERT INTO ek_message (sender_id, receiver_id, content, is_read, created_at, updated_at) "
        "VALUES (?, ?, ?, 0, ?, ?)",
        (my_id, mentor_id, content, now_str, now_str),
        fetch="none"
    )

    # 방금 저장한 메시지의 msg_idx 조회
    msg_row = execute_query(
        "SELECT msg_idx FROM ek_message "
        "WHERE sender_id = ? AND receiver_id = ? "
        "ORDER BY created_at DESC LIMIT 1",
        (my_id, mentor_id),
        fetch="one"
    )
    msg_idx = msg_row["msg_idx"] if msg_row else None

    # 토큰 생성 및 이메일 알림 (멘토 이메일이 있을 경우)
    if msg_idx:
        token = uuid.uuid4().hex
        expires = (datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
        execute_query(
            "INSERT INTO ek_message_token (token, msg_idx, mentor_id, expires_at, is_used, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (token, msg_idx, mentor_id, expires, now_str),
            fetch="none"
        )

        # 멘토 이메일 조회 (mem_MbrId가 이메일 형식인 경우 그대로 사용)
        mentor_info = execute_query(
            "SELECT mem_MbrId, mem_MbrName, mem_nickname "
            "FROM ek_Member WHERE mem_MbrId = ?",
            (mentor_id,),
            fetch="one"
        )
        mentor_email = mentor_id if "@" in mentor_id else None

        if mentor_email and mentor_info:
            base_url = _get_base_url(request)
            reply_url = f"{base_url}/message/reply?token={token}"
            subject, html_body = build_mentor_notification_email(
                student_name=user["name"],
                message_content=content,
                reply_url=reply_url,
            )
            background_tasks.add_task(send_email, mentor_email, subject, html_body)

    return RedirectResponse(f"/message/chat/{mentor_id}", status_code=303)


# ===== 멘토 답변 기능 (토큰 기반, 로그인 불필요) =====


def _validate_token(token_str: str) -> dict | None:
    """토큰 검증: 유효하고 미사용이면 토큰 정보 반환"""
    token_row = execute_query(
        "SELECT token_idx, token, msg_idx, mentor_id, expires_at, is_used "
        "FROM ek_message_token WHERE token = ?",
        (token_str,),
        fetch="one"
    )
    if not token_row:
        return None

    # 만료 확인
    try:
        expires = datetime.strptime(token_row["expires_at"][:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None

    if datetime.now() > expires:
        return None

    # 사용 여부 (is_used=1이면 이미 사용됨, 하지만 답변 페이지는 볼 수 있게)
    return token_row


@router.get("/reply", response_class=HTMLResponse)
async def reply_page(request: Request, token: str = ""):
    """멘토 답변 페이지 (로그인 불필요)"""
    if not token:
        return HTMLResponse(
            "<div style='text-align:center;padding:60px;font-family:sans-serif;'>"
            "<h2>잘못된 접근입니다</h2></div>",
            status_code=400,
        )

    token_row = _validate_token(token)
    if not token_row:
        return HTMLResponse(
            "<div style='text-align:center;padding:60px;font-family:sans-serif;'>"
            "<h2>링크가 만료되었거나 유효하지 않습니다</h2>"
            "<p>새 메시지를 받으면 새 링크가 발송됩니다.</p></div>",
            status_code=410,
        )

    mentor_id = token_row["mentor_id"]
    msg_idx = token_row["msg_idx"]
    is_used = token_row["is_used"]

    # 원본 메시지에서 수강생 ID 조회
    orig_msg = execute_query(
        "SELECT msg_idx, sender_id, receiver_id, content, created_at "
        "FROM ek_message WHERE msg_idx = ?",
        (msg_idx,),
        fetch="one"
    )
    if not orig_msg:
        return HTMLResponse(
            "<div style='text-align:center;padding:60px;font-family:sans-serif;'>"
            "<h2>메시지를 찾을 수 없습니다</h2></div>",
            status_code=404,
        )

    student_id = orig_msg["sender_id"]

    # 수강생 정보
    student_info = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg "
        "FROM ek_Member WHERE mem_MbrId = ?",
        (student_id,),
        fetch="one"
    )
    student_name = ""
    if student_info:
        student_name = student_info.get("mem_nickname") or student_info.get("mem_MbrName", "")

    # 멘토 정보
    mentor_info = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname "
        "FROM ek_Member WHERE mem_MbrId = ?",
        (mentor_id,),
        fetch="one"
    )
    mentor_name = ""
    if mentor_info:
        mentor_name = mentor_info.get("mem_nickname") or mentor_info.get("mem_MbrName", "")

    # 대화 히스토리 (이 수강생과 이 멘토 사이의 모든 메시지)
    chat_history = execute_query(
        "SELECT msg_idx, sender_id, receiver_id, content, created_at "
        "FROM ek_message "
        "WHERE (sender_id = ? AND receiver_id = ?) "
        "   OR (sender_id = ? AND receiver_id = ?) "
        "ORDER BY created_at ASC",
        (student_id, mentor_id, mentor_id, student_id),
        fetch="all"
    )

    messages = []
    for m in chat_history:
        is_student = m["sender_id"] == student_id
        messages.append({
            "content": m["content"],
            "is_student": is_student,
            "sender_name": student_name if is_student else mentor_name,
            "time": _format_chat_time(m.get("created_at", "")),
        })

    # 수강생 학습 이력 (최근 수업 예약)
    learning_history = execute_query(
        "SELECT B.book_date, B.book_start_time, B.book_end_time, "
        "M.mem_MbrName AS teacher_name "
        "FROM ek_Booking B "
        "LEFT JOIN ek_Member M ON B.book_teacher_id = M.mem_MbrId "
        "WHERE B.book_member_id = ? AND B.book_state = 1 "
        "ORDER BY B.book_date DESC LIMIT 5",
        (student_id,),
        fetch="all"
    )

    return templates.TemplateResponse(request, "message/reply.html", {
        "token": token,
        "is_used": is_used,
        "student_name": student_name,
        "student_id": student_id,
        "mentor_name": mentor_name,
        "mentor_id": mentor_id,
        "messages": messages,
        "learning_history": learning_history,
    })


@router.post("/reply", response_class=HTMLResponse)
async def submit_reply(
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Form(),
    content: str = Form(),
):
    """멘토 답변 등록 (로그인 불필요)"""
    token_row = _validate_token(token)
    if not token_row:
        return HTMLResponse(
            "<div style='text-align:center;padding:60px;font-family:sans-serif;'>"
            "<h2>링크가 만료되었거나 유효하지 않습니다</h2></div>",
            status_code=410,
        )

    mentor_id = token_row["mentor_id"]
    msg_idx = token_row["msg_idx"]

    # 원본 메시지에서 수강생 ID 조회
    orig_msg = execute_query(
        "SELECT sender_id FROM ek_message WHERE msg_idx = ?",
        (msg_idx,),
        fetch="one"
    )
    if not orig_msg:
        return HTMLResponse(
            "<div style='text-align:center;padding:60px;font-family:sans-serif;'>"
            "<h2>메시지를 찾을 수 없습니다</h2></div>",
            status_code=404,
        )

    student_id = orig_msg["sender_id"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 답변 메시지 저장 (parent_msg_idx로 원본 메시지 참조)
    execute_query(
        "INSERT INTO ek_message (sender_id, receiver_id, content, parent_msg_idx, is_read, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?)",
        (mentor_id, student_id, content, msg_idx, now_str, now_str),
        fetch="none"
    )

    # 토큰 사용 처리
    execute_query(
        "UPDATE ek_message_token SET is_used = 1 WHERE token = ?",
        (token,),
        fetch="none"
    )

    # 수강생 이메일 알림
    student_email = student_id if "@" in student_id else None
    if student_email:
        mentor_info = execute_query(
            "SELECT mem_MbrName, mem_nickname FROM ek_Member WHERE mem_MbrId = ?",
            (mentor_id,),
            fetch="one"
        )
        mentor_display = ""
        if mentor_info:
            mentor_display = mentor_info.get("mem_nickname") or mentor_info.get("mem_MbrName", "")

        base_url = _get_base_url(request)
        chat_url = f"{base_url}/message/chat/{mentor_id}"
        subject, html_body = build_student_notification_email(
            mentor_name=mentor_display,
            message_content=content,
            chat_url=chat_url,
        )
        background_tasks.add_task(send_email, student_email, subject, html_body)

    # 답변 완료 후 같은 페이지로 리다이렉트 (답변 완료 표시)
    return RedirectResponse(f"/message/reply?token={token}", status_code=303)
