# app/routers/payment.py
# 토스 페이먼츠 결제 라우터
# URL 패턴: /booking/payment/*
# 기존 /booking/payment (패키지 목록)은 booking_pages.py에 유지

import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.auth_service import get_current_user
from app.services.payment_service import (
    generate_order_id, get_package, confirm_payment, create_settlement
)
from app.config import settings
from app.services.agreement_service import needs_agreement

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/booking/payment", tags=["결제"])
templates = Jinja2Templates(directory="templates")


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, package_code: int,
                        user=Depends(get_current_user)):
    """결제 체크아웃 페이지 (토스 위젯 포함)"""
    if not user:
        return RedirectResponse("/booking/")
    if needs_agreement(user["mem_MbrId"]):
        return RedirectResponse("/booking/agreement/guide", status_code=303)

    pkg = get_package(package_code)
    if not pkg:
        return RedirectResponse("/booking/payment")

    order_id = generate_order_id()

    # 현재 호스트 기반 URL 생성 (localhost 하드코딩 방지)
    base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(request, "booking/payment_checkout.html", {
        "user": user,
        "package": pkg,
        "order_id": order_id,
        "client_key": settings.TOSS_CLIENT_KEY,
        "success_url": f"{base_url}/booking/payment/success",
        "fail_url": f"{base_url}/booking/payment/fail",
    })


@router.get("/success", response_class=HTMLResponse)
async def payment_success(request: Request,
                          paymentKey: str, orderId: str, amount: int,
                          user=Depends(get_current_user)):
    """토스 결제 성공 콜백 → 서버에서 결제 승인 후 수강권 생성"""
    if not user:
        return RedirectResponse("/booking/")

    # 1. 토스 API로 결제 승인
    result = await confirm_payment(paymentKey, orderId, amount)

    if result.get("error"):
        # 승인 실패 → 실패 페이지
        return templates.TemplateResponse(request, "booking/payment_fail.html", {
            "error_code": result.get("code", "UNKNOWN"),
            "error_message": result.get("message", "결제 승인에 실패했습니다."),
        })

    # 2. 주문 정보에서 패키지 코드 추출 (토스 응답에서 amount로 패키지 매칭)
    from app.database import execute_query
    pkg = execute_query(
        "SELECT * FROM ek_Package WHERE price = ?",
        (amount,),
        fetch="one"
    )

    if not pkg:
        return templates.TemplateResponse(request, "booking/payment_fail.html", {
            "error_code": "PACKAGE_NOT_FOUND",
            "error_message": "해당 금액의 패키지를 찾을 수 없습니다.",
        })

    # 보안: 토스가 승인한 금액과 패키지 가격 일치 확인 (결제 금액 변조 방지)
    confirmed_amount = result.get("totalAmount", amount)
    if confirmed_amount != pkg["price"]:
        logger.warning(
            "결제 금액 불일치! user=%s, orderId=%s, paid=%s, pkg_price=%s",
            user["mem_MbrId"], orderId, confirmed_amount, pkg["price"]
        )
        return templates.TemplateResponse(request, "booking/payment_fail.html", {
            "error_code": "AMOUNT_MISMATCH",
            "error_message": "결제 금액이 패키지 가격과 일치하지 않습니다. 관리자에게 문의해주세요.",
        })

    # 3. 수강권 생성
    settle_code = create_settlement(
        mem_id=user["mem_MbrId"],
        package_code=pkg["package_code"],
        amount=confirmed_amount,
    )

    return templates.TemplateResponse(request, "booking/payment_success.html", {
        "package_name": pkg["package_name"],
        "amount": f"{amount:,}",
        "date": result.get("approvedAt", "")[:10],
        "settle_code": settle_code,
        "order_id": orderId,
    })


@router.get("/fail", response_class=HTMLResponse)
async def payment_fail(request: Request,
                       code: str = "", message: str = ""):
    """토스 결제 실패 콜백"""
    return templates.TemplateResponse(request, "booking/payment_fail.html", {
        "error_code": code,
        "error_message": message or "결제가 취소되었거나 실패했습니다.",
    })
