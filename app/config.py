# app/config.py
# 환경변수 설정 (pydantic-settings)
# .env 파일에서 로드

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # DB 모드: development(SQLite) / production(MS-SQL)
    DB_MODE: str = "development"

    # DB 연결 (production 모드에서만 사용)
    DB_SERVER: str = "kevinsaem.com,1433"
    DB_NAME: str = "kevinsaem_db"
    DB_USER: str = ""
    DB_PASSWORD: str = ""

    # JWT
    JWT_SECRET: str = "change-this-to-random-secret-key"
    JWT_EXPIRE_MINUTES: int = 30

    # 카카오 알림톡
    KAKAO_API_KEY: str = ""
    KAKAO_SENDER_KEY: str = ""

    # 카카오 로그인
    KAKAO_REST_API_KEY: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:8500/auth/kakao/callback"

    # 토스 페이먼츠
    TOSS_CLIENT_KEY: str = ""
    TOSS_SECRET_KEY: str = ""

    # 관리자
    ADMIN_PASSWORD: str = "admin1234"
    ADMIN_JWT_EXPIRE_MINUTES: int = 480  # 8시간

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8000", "https://booking.kevinsaem.com"]

    # 강사 구분
    TEACHER_TYPE_FIELD: str = "mem_MbrType"
    TEACHER_TYPE_VALUE: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
