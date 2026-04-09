# app/routers/auth.py
# 카카오 로그인 OAuth 라우터

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.config import settings
from app.services.auth_service import create_jwt
from app.database import execute_query

router = APIRouter(prefix="/auth", tags=["인증"])

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"


@router.get("/kakao/login")
async def kakao_login():
    """카카오 로그인 페이지로 이동"""
    url = (
        f"{KAKAO_AUTH_URL}"
        f"?client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )
    return RedirectResponse(url)


@router.get("/kakao/callback")
async def kakao_callback(request: Request, code: str = None, error: str = None):
    """카카오 로그인 콜백 처리"""
    if error or not code:
        return RedirectResponse("/booking/?error=카카오 로그인이 취소되었습니다")

    # 1. 인가코드 -> 액세스 토큰 교환
    async with httpx.AsyncClient() as client:
        token_res = await client.post(KAKAO_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "client_secret": settings.KAKAO_CLIENT_SECRET,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        })

    if token_res.status_code != 200:
        import urllib.parse
        detail = urllib.parse.quote(f"status:{token_res.status_code} body:{token_res.text}")
        return RedirectResponse(f"/booking/?error={detail}")

    access_token = token_res.json().get("access_token")

    # 2. 액세스 토큰 -> 사용자 정보 조회
    async with httpx.AsyncClient() as client:
        user_res = await client.get(KAKAO_USER_URL, headers={
            "Authorization": f"Bearer {access_token}"
        })

    if user_res.status_code != 200:
        return RedirectResponse("/booking/?error=사용자 정보를 가져올 수 없습니다")

    kakao_data = user_res.json()
    kakao_id = str(kakao_data["id"])
    kakao_account = kakao_data.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    nickname = profile.get("nickname", "")
    real_name = kakao_account.get("name", "") or nickname

    # 3. ek_Member에서 기존 회원 확인
    mem_id = f"KKO{kakao_id[-8:]}"
    existing = execute_query(
        "SELECT mem_MbrId, mem_MbrName, mem_nickname, mem_MbrType FROM ek_Member WHERE mem_MbrId = ?",
        (mem_id,),
        fetch="one"
    )

    if existing:
        # 기존 회원
        role = "student"
    else:
        # 신규 가입 → ek_Member에 등록 (mem_MbrType=2: 수강생)
        phone_raw = kakao_account.get("phone_number", "")
        phone = ""
        if phone_raw:
            digits = phone_raw.replace("+82 ", "0").replace("-", "").replace(" ", "")
            if len(digits) == 11:
                phone = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            else:
                phone = digits

        execute_query(
            "INSERT INTO ek_Member "
            "(mem_MbrId, mem_MbrName, mem_nickname, mem_TelNo2, mem_TelNo3, "
            " mem_MbrType, mem_edate) "
            "VALUES (?, ?, ?, ?, ?, '2', GETDATE())",
            (mem_id, real_name, nickname, phone, phone),
            fetch="none"
        )
        role = "student"

    # 4. 수강권 확인 (없으면 settle_code=0)
    settle = execute_query(
        "SELECT settle_code FROM ek_Settlement WHERE settle_mbr_id = ? AND settle_state = 1 ORDER BY settle_date DESC",
        (mem_id,),
        fetch="one"
    )
    settle_code = settle["settle_code"] if settle else 0

    # 5. JWT 발급 + 쿠키 설정
    display_name = nickname or real_name
    user = {
        "mem_MbrId": mem_id,
        "name": display_name,
        "role": role,
        "settle_code": settle_code,
    }
    token = create_jwt(user)

    # 6. 리다이렉트
    response = RedirectResponse("/booking/", status_code=302)
    is_prod = settings.DB_MODE == "production"
    response.set_cookie(
        "token", token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response
