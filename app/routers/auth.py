# app/routers/auth.py
# 카카오 로그인 OAuth 라우터 (역할 기반 라우팅)

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
    """카카오 로그인 콜백 처리 - 역할 기반 라우팅"""
    if error or not code:
        return RedirectResponse("/booking/?error=카카오 로그인이 취소되었습니다")

    # 1. 인가코드 -> 액세스 토큰 교환
    async with httpx.AsyncClient() as client:
        token_res = await client.post(KAKAO_TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        })

    if token_res.status_code != 200:
        return RedirectResponse("/booking/?error=카카오 인증에 실패했습니다")

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
    profile_img = profile.get("profile_image_url", "")
    email = kakao_account.get("email", "")
    real_name = kakao_account.get("name", "") or nickname  # 실명 (없으면 닉네임)

    # 3. DB에서 기존 회원 확인 또는 신규 가입
    existing = execute_query(
        "SELECT * FROM kakao_members WHERE kakao_id = ?",
        (kakao_id,),
        fetch="one"
    )

    if existing:
        # 기존 회원 -> 프로필 업데이트
        execute_query(
            "UPDATE kakao_members SET nickname = ?, profile_img = ?, email = ? WHERE kakao_id = ?",
            (nickname, profile_img, email, kakao_id),
            fetch="none"
        )
        mem_id = existing["mem_id"]
        role = existing.get("role", "student") or "student"
    else:
        # 신규 가입 (기본 역할: student)
        mem_id = f"KKO{kakao_id[-8:]}"
        role = "student"

        # kakao_members 등록
        execute_query(
            "INSERT INTO kakao_members (kakao_id, mem_id, nickname, profile_img, email, role) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (kakao_id, mem_id, nickname, profile_img, email, role),
            fetch="none"
        )

        # ek_Member에도 등록 (기존 시스템 호환)
        import hashlib

        phone_raw = kakao_account.get("phone_number", "")
        # 카카오 전화번호 형식: +82 10-1234-5678 → 010-1234-5678
        phone = ""
        if phone_raw:
            digits = phone_raw.replace("+82 ", "0").replace("-", "").replace(" ", "")
            if len(digits) == 11:
                phone = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            else:
                phone = digits

        # 비밀번호: kakao_id + 전화번호 뒤 4자리를 MD5 해시 (예측 방지)
        phone_last4 = phone.replace("-", "")[-4:] if phone else "0000"
        md5_pwd = hashlib.md5(f"{kakao_id}{phone_last4}".encode()).hexdigest()

        execute_query(
            "INSERT OR IGNORE INTO ek_Member "
            "(mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg, mem_TelNo2, mem_TelNo3, "
            " mem_Pwd, mem_MbrType, mem_edate, injeung_code, edc_idx) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, '2', datetime('now'), NULL, 0)",
            (mem_id, real_name, nickname, profile_img, phone, phone, md5_pwd),
            fetch="none"
        )

    # 4. 수강권 확인 (없으면 settle_code=0)
    settle = execute_query(
        "SELECT settle_code FROM ek_Settlement WHERE settle_mbr_id = ? AND settle_state = 1 ORDER BY settle_date DESC",
        (mem_id,),
        fetch="one"
    )
    settle_code = settle["settle_code"] if settle else 0

    # 5. JWT 발급 (역할 포함) + 쿠키 설정
    user = {
        "mem_MbrId": mem_id,
        "name": nickname,
        "role": role,
        "settle_code": settle_code,
    }
    token = create_jwt(user)

    # 6. 역할 기반 리다이렉트
    redirect_map = {
        "admin": "/admin/",
        "teacher": "/teacher/",
        "student": "/booking/",
    }
    redirect_url = redirect_map.get(role, "/booking/")

    response = RedirectResponse(redirect_url, status_code=302)
    is_prod = settings.DB_MODE == "production"
    response.set_cookie(
        "token", token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return response
