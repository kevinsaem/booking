# app/services/auth_service.py
# 인증 서비스: 로그인, JWT 발급/검증, 인증번호 발급

from fastapi import Request
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.config import settings
from app.database import execute_query


def login(name: str, code: str) -> dict | None:
    """이름 + 인증번호로 로그인
    
    Returns:
        성공 시 사용자 정보 dict, 실패 시 None
    """
    row = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg, "
        "mem_TelNo3, edc_idx, injeung_code "
        "FROM ek_Member "
        "WHERE mem_MbrName = ? AND injeung_code = ?",
        (name, code),
        fetch="one"
    )
    if not row:
        return None

    # 유효한 결제(수강권) 조회
    settle = execute_query(
        "SELECT settle_code, settle_package_code "
        "FROM ek_Settlement "
        "WHERE settle_mbr_id = ? AND settle_state = 1 "
        "ORDER BY settle_date DESC",
        (row["mem_MbrId"],),
        fetch="one"
    )

    # 캠퍼스명 조회
    campus = execute_query(
        "SELECT edc_Name FROM ek_EduCenter WHERE edc_Idx = ?",
        (row["edc_idx"],),
        fetch="one"
    )

    # 패키지명 조회
    pkg_name = "AI활용 과정"
    if settle:
        pkg = execute_query(
            "SELECT package_name FROM ek_Package WHERE package_code = ?",
            (settle["settle_package_code"],),
            fetch="one"
        )
        if pkg:
            pkg_name = pkg["package_name"]

    return {
        "mem_MbrId": row["mem_MbrId"],
        "name": row["mem_MbrName"],
        "nickname": row.get("mem_nickname", ""),
        "img": row.get("mem_MbrImg", ""),
        "phone": row.get("mem_TelNo3", ""),
        "settle_code": settle["settle_code"] if settle else 0,
        "package_code": settle["settle_package_code"] if settle else 0,
        "campus_name": campus["edc_Name"] if campus else "케빈샘AI코딩",
        "package_name": pkg_name,
    }


def create_jwt(user: dict) -> str:
    """JWT 토큰 생성 (httponly 쿠키에 저장용)"""
    payload = {
        "sub": user["mem_MbrId"],
        "name": user["name"],
        "settle_code": user["settle_code"],
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


async def get_current_user(request: Request) -> dict | None:
    """JWT 쿠키에서 현재 사용자 정보 추출
    
    Depends(get_current_user)로 사용
    로그인 안 된 경우 None 반환 → 라우터에서 로그인 페이지 리다이렉트
    """
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return {
            "mem_MbrId": payload["sub"],
            "name": payload["name"],
            "settle_code": payload["settle_code"],
        }
    except JWTError:
        return None


def generate_auth_code() -> str:
    """4자리 랜덤 인증번호 생성"""
    import random
    return str(random.randint(1000, 9999))


def update_auth_code(mem_id: str, new_code: str) -> bool:
    """인증번호 업데이트 (재발급 시)"""
    affected = execute_query(
        "UPDATE ek_Member SET injeung_code = ? WHERE mem_MbrId = ?",
        (new_code, mem_id),
        fetch="none"
    )
    return affected > 0
