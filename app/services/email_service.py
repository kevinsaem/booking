# app/services/email_service.py
# Gmail SMTP 이메일 발송 서비스
# BackgroundTasks로 비동기 발송

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings


def send_email(to: str, subject: str, body: str, html: bool = True) -> bool:
    """Gmail SMTP로 이메일 발송

    Args:
        to: 수신자 이메일
        subject: 제목
        body: 본문 (HTML 또는 텍스트)
        html: True면 HTML, False면 plain text

    Returns:
        성공 여부
    """
    if not settings.SMTP_EMAIL or not settings.SMTP_PASSWORD:
        print("⚠️ SMTP 설정 없음 — 이메일 발송 건너뜀")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"케빈샘AI코딩학원 <{settings.SMTP_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = subject

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)

        print(f"📧 이메일 발송 완료: {to}")
        return True
    except Exception as e:
        print(f"📧 이메일 발송 실패: {e}")
        return False


def build_mentor_notification_email(
    student_name: str,
    message_content: str,
    reply_url: str,
) -> tuple[str, str]:
    """멘토에게 보내는 알림 이메일 (제목, HTML본문) 생성

    Returns:
        (subject, html_body)
    """
    subject = f"[케빈샘AI코딩학원] {student_name}님이 메시지를 보냈습니다"
    html_body = f"""
    <div style="max-width:480px;margin:0 auto;font-family:'Noto Sans KR',sans-serif;padding:20px;">
        <div style="background:#43A047;color:white;padding:16px 20px;border-radius:12px 12px 0 0;">
            <h2 style="margin:0;font-size:16px;">케빈샘AI코딩학원 메시지 알림</h2>
        </div>
        <div style="border:1px solid #E0E0E0;border-top:none;padding:20px;border-radius:0 0 12px 12px;">
            <p style="color:#424242;font-size:14px;margin:0 0 12px;">
                <strong>{student_name}</strong>님이 메시지를 보냈습니다.
            </p>
            <div style="background:#F5F5F5;padding:12px 16px;border-radius:8px;margin:0 0 20px;">
                <p style="color:#616161;font-size:13px;margin:0;white-space:pre-wrap;">{message_content[:200]}{'...' if len(message_content) > 200 else ''}</p>
            </div>
            <a href="{reply_url}"
               style="display:inline-block;background:#43A047;color:white;text-decoration:none;
                      padding:12px 24px;border-radius:8px;font-size:14px;font-weight:bold;">
                답변하기
            </a>
            <p style="color:#BDBDBD;font-size:11px;margin:16px 0 0;">
                이 링크는 48시간 동안 유효합니다.
            </p>
        </div>
    </div>
    """
    return subject, html_body


def build_student_notification_email(
    mentor_name: str,
    message_content: str,
    chat_url: str,
) -> tuple[str, str]:
    """수강생에게 보내는 답변 알림 이메일 (제목, HTML본문) 생성

    Returns:
        (subject, html_body)
    """
    subject = f"[케빈샘AI코딩학원] {mentor_name} 멘토가 답변을 보냈습니다"
    html_body = f"""
    <div style="max-width:480px;margin:0 auto;font-family:'Noto Sans KR',sans-serif;padding:20px;">
        <div style="background:#43A047;color:white;padding:16px 20px;border-radius:12px 12px 0 0;">
            <h2 style="margin:0;font-size:16px;">케빈샘AI코딩학원 메시지 알림</h2>
        </div>
        <div style="border:1px solid #E0E0E0;border-top:none;padding:20px;border-radius:0 0 12px 12px;">
            <p style="color:#424242;font-size:14px;margin:0 0 12px;">
                <strong>{mentor_name}</strong> 멘토가 답변을 보냈습니다.
            </p>
            <div style="background:#F5F5F5;padding:12px 16px;border-radius:8px;margin:0 0 20px;">
                <p style="color:#616161;font-size:13px;margin:0;white-space:pre-wrap;">{message_content[:200]}{'...' if len(message_content) > 200 else ''}</p>
            </div>
            <a href="{chat_url}"
               style="display:inline-block;background:#43A047;color:white;text-decoration:none;
                      padding:12px 24px;border-radius:8px;font-size:14px;font-weight:bold;">
                대화 확인하기
            </a>
        </div>
    </div>
    """
    return subject, html_body
