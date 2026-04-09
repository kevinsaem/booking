# app/dependencies.py
# 공통 의존성: 인증 필수 체크 등

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from app.services.auth_service import get_current_user


async def require_user(request: Request, user=Depends(get_current_user)):
    """로그인 필수 의존성

    로그인 안 된 경우 로그인 페이지로 리다이렉트
    로그인 된 경우 user dict 반환
    """
    if not user:
        raise _LoginRequired()
    return user


class _LoginRequired(Exception):
    """로그인 필요 예외 (exception_handler에서 처리)"""
    pass
