# app/services/auth_service.py
# 인증 서비스: JWT 발급/검증, 역할 기반 인증

from fastapi import Request
from jose import jwt, JWTError
from datetime import datetime, timedelta
from app.config import settings
from app.database import execute_query


def create_jwt(user: dict) -> str:
    """JWT 토큰 생성 (httponly 쿠키에 저장용)"""
    payload = {
        "sub": user["mem_MbrId"],
        "name": user["name"],
        "role": user.get("role", "student"),
        "settle_code": user.get("settle_code", 0),
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


async def get_current_user(request: Request) -> dict | None:
    """JWT 쿠키에서 현재 사용자 정보 추출

    Depends(get_current_user)로 사용
    로그인 안 된 경우 None 반환 -> 라우터에서 로그인 페이지 리다이렉트
    """
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return {
            "mem_MbrId": payload["sub"],
            "name": payload["name"],
            "role": payload.get("role", "student"),
            "settle_code": payload.get("settle_code", 0),
        }
    except JWTError:
        return None


async def get_current_admin(request: Request) -> dict | None:
    """현재 사용자가 admin이면 반환, 아니면 None"""
    user = await get_current_user(request)
    if user and user.get("role") == "admin":
        return user
    return None


async def get_current_teacher(request: Request) -> dict | None:
    """현재 사용자가 teacher이면 반환, 아니면 None"""
    user = await get_current_user(request)
    if user and user.get("role") == "teacher":
        return user
    return None


def generate_auth_code() -> str:
    """4자리 랜덤 인증번호 생성 (암호학적 안전)"""
    import secrets
    return str(secrets.randbelow(9000) + 1000)


def update_auth_code(mem_id: str, new_code: str) -> bool:
    """인증번호 업데이트 (재발급 시)"""
    affected = execute_query(
        "UPDATE ek_Member SET injeung_code = ? WHERE mem_MbrId = ?",
        (new_code, mem_id),
        fetch="none"
    )
    return affected > 0
