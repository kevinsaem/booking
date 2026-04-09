# app/routers/agreement.py
# 교육 서비스 이용 계약서 전자서명 라우터
# URL 패턴: /booking/agreement/*

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user
from app.services import agreement_service
from fastapi import Depends

router = APIRouter(prefix="/booking/agreement", tags=["전자서명"])
templates = Jinja2Templates(directory="templates")


@router.get("/guide", response_class=HTMLResponse)
async def agreement_guide(request: Request, user=Depends(get_current_user)):
    """서명 필요 안내 페이지 (3초 카운트다운 후 자동 이동)"""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/booking/", status_code=303)

    return templates.TemplateResponse(request, "booking/agreement_guide.html", {
        "user": user,
    })


@router.get("/", response_class=HTMLResponse)
async def view_agreement(request: Request, user=Depends(get_current_user)):
    """계약서 열람 + 서명 페이지"""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/booking/", status_code=303)

    template = agreement_service.get_active_template()
    if not template:
        raise HTTPException(status_code=404, detail="계약서를 찾을 수 없습니다.")

    already_signed = agreement_service.check_student_signed(
        user["mem_MbrId"], template["id"]
    )
    if already_signed:
        return templates.TemplateResponse(request, "booking/agreement_signed.html", {
            "user": user,
            "already_signed": True,
        })

    # 수강생 정보
    from app.database import execute_query
    member = execute_query(
        "SELECT mem_MbrName, mem_TelNo3 FROM ek_Member WHERE mem_MbrId = ?",
        (user["mem_MbrId"],),
        fetch="one"
    )

    # 계약서 본문에 수강생 정보 자동 채우기
    from datetime import datetime
    content = template["content"]
    content = content.replace("{{수강생_성명}}", member["mem_MbrName"] if member else "")
    content = content.replace("{{수강생_연락처}}", member.get("mem_TelNo3") or "-" if member else "")
    content = content.replace("{{계약_체결일}}", datetime.now().strftime("%Y년 %m월 %d일"))
    # 전자서명 시 서명 행 제거 (서명란은 별도 서명 패드로 대체)
    content = content.replace("| 서명 | {{교육기관_서명}} |\n", "")
    content = content.replace("| 서명 | {{수강생_서명}} |\n", "")
    content = content.replace("{{서명_일시}}", "")
    content = content.replace("{{서명_IP}}", "")
    content = content.replace("{{서명_디바이스}}", "")
    content = content.replace("{{문서_해시}}", "")

    # Markdown → HTML 변환
    content_html = _markdown_to_html(content)
    document_hash = agreement_service.compute_document_hash(template["content"])

    return templates.TemplateResponse(request, "booking/agreement_view.html", {
        "user": user,
        "template": template,
        "content_html": content_html,
        "document_hash": document_hash,
        "member": member,
    })


@router.post("/sign")
async def sign_agreement(
    request: Request,
    template_id: int = Form(...),
    document_hash: str = Form(...),
    signature_data: str = Form(...),
    user=Depends(get_current_user),
):
    """전자서명 제출"""
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    # 중복 서명 방지
    if agreement_service.check_student_signed(user["mem_MbrId"], template_id):
        raise HTTPException(status_code=400, detail="이미 서명한 계약서입니다.")

    # 서명 데이터 검증
    if not signature_data or not signature_data.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=400, detail="유효하지 않은 서명 데이터입니다.")

    # 서명 이미지 크기 제한 (200KB)
    if len(signature_data) > 200_000:
        raise HTTPException(status_code=400, detail="서명 이미지가 너무 큽니다.")

    # 클라이언트 정보
    ip_address = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    device_info = agreement_service.detect_device(user_agent)

    # 저장
    result = agreement_service.save_signature(
        mem_mbr_id=user["mem_MbrId"],
        template_id=template_id,
        signature_image=signature_data,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
        document_hash=document_hash,
    )

    # 저장 실패 시
    if not result:
        raise HTTPException(status_code=500, detail="서명 저장에 실패했습니다. 다시 시도해주세요.")

    # 저장 성공 → 완료 페이지로 리다이렉트 (PRG 패턴)
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/booking/agreement/done", status_code=303)


@router.get("/done", response_class=HTMLResponse)
async def agreement_done(request: Request, user=Depends(get_current_user)):
    """서명 완료 페이지"""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/booking/", status_code=303)
    return templates.TemplateResponse(request, "booking/agreement_signed.html", {
        "user": user,
        "just_signed": True,
    })


@router.get("/history", response_class=HTMLResponse)
async def signature_history(request: Request, user=Depends(get_current_user)):
    """서명 이력 조회 (MY페이지에서 접근)"""
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/booking/", status_code=303)

    history = agreement_service.get_signature_history(user["mem_MbrId"])

    # 계약서 본문 (수강생 정보 채워서)
    content_html = ""
    template = agreement_service.get_active_template()
    if template:
        from app.database import execute_query
        from datetime import datetime
        member = execute_query(
            "SELECT mem_MbrName, mem_TelNo3 FROM ek_Member WHERE mem_MbrId = ?",
            (user["mem_MbrId"],),
            fetch="one"
        )
        content = template["content"]
        content = content.replace("{{수강생_성명}}", member["mem_MbrName"] if member else "")
        content = content.replace("{{수강생_연락처}}", member.get("mem_TelNo3") or "-" if member else "")
        content = content.replace("{{계약_체결일}}", history[0]["agreed_at"][:10] if history else "")
        content = content.replace("| 서명 | {{교육기관_서명}} |\n", "")
        content = content.replace("| 서명 | {{수강생_서명}} |\n", "")
        content = content.replace("{{서명_일시}}", "")
        content = content.replace("{{서명_IP}}", "")
        content = content.replace("{{서명_디바이스}}", "")
        content = content.replace("{{문서_해시}}", "")
        content_html = _markdown_to_html(content)

    return templates.TemplateResponse(request, "booking/agreement_history.html", {
        "user": user,
        "history": history,
        "content_html": content_html,
    })


def _markdown_to_html(md_text: str) -> str:
    """Markdown을 간단한 HTML로 변환"""
    try:
        import markdown
        return markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    except ImportError:
        # markdown 패키지 없으면 기본 변환
        html = md_text
        html = html.replace("\n\n", "</p><p>")
        html = html.replace("\n", "<br>")
        return f"<p>{html}</p>"
