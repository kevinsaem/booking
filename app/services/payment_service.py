# app/services/payment_service.py
# 토스 페이먼츠 결제 서비스
# - 결제 승인 (confirm)
# - 수강권 생성 (settlement)
# - 주문 ID 생성

import base64
import secrets
import httpx
from datetime import datetime, timedelta
from app.config import settings
from app.database import execute_query


def generate_order_id() -> str:
    """고유 주문 ID 생성 (ORDER-YYYYMMDD-XXXXX)"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(3).upper()[:5]
    return f"ORDER-{date_str}-{random_part}"


def get_package(package_code: int) -> dict | None:
    """패키지 정보 조회"""
    return execute_query(
        "SELECT * FROM ek_Package WHERE package_code = ?",
        (package_code,),
        fetch="one"
    )


async def confirm_payment(payment_key: str, order_id: str, amount: int) -> dict:
    """토스 페이먼츠 결제 승인 API 호출

    Returns:
        성공 시 토스 응답 dict, 실패 시 {"error": True, "message": "..."} 반환
    """
    secret_key = settings.TOSS_SECRET_KEY
    # Basic 인증: secret_key + ":" 를 base64 인코딩
    auth_string = base64.b64encode(f"{secret_key}:".encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.tosspayments.com/v1/payments/confirm",
            headers={
                "Authorization": f"Basic {auth_string}",
                "Content-Type": "application/json",
            },
            json={
                "paymentKey": payment_key,
                "orderId": order_id,
                "amount": amount,
            },
            timeout=30.0,
        )

    if response.status_code == 200:
        return response.json()
    else:
        error_data = response.json()
        return {
            "error": True,
            "code": error_data.get("code", "UNKNOWN"),
            "message": error_data.get("message", "결제 승인에 실패했습니다."),
        }


def create_settlement(mem_id: str, package_code: int, amount: int) -> int:
    """수강권(ek_Settlement) 레코드 생성

    Returns:
        생성된 settle_code
    """
    now = datetime.now()
    pkg = get_package(package_code)
    month_cnt = pkg["month_cnt"] if pkg else 1

    settle_date = now.strftime("%Y-%m-%d")
    settle_sdate = settle_date
    settle_edate = (now + timedelta(days=30 * month_cnt)).strftime("%Y-%m-%d")

    execute_query(
        "INSERT INTO ek_Settlement "
        "(settle_mbr_id, settle_package_code, settle_amount, settle_state, "
        "settle_date, settle_sdate, settle_edate) "
        "VALUES (?, ?, ?, 1, ?, ?, ?)",
        (mem_id, package_code, amount, settle_date, settle_sdate, settle_edate),
        fetch="none"
    )

    # 방금 생성된 settle_code 조회
    row = execute_query(
        "SELECT settle_code FROM ek_Settlement "
        "WHERE settle_mbr_id = ? ORDER BY settle_code DESC LIMIT 1",
        (mem_id,),
        fetch="one"
    )
    return row["settle_code"] if row else 0
