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
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:8000", "https://booking.kevinsaem.com"]
    
    # 강사 구분 필드 (ek_Member에서 성인 1:1 AI과정 강사 식별)
    TEACHER_TYPE_FIELD: str = "mem_MbrType"
    TEACHER_TYPE_VALUE: str = ""  # 실제 값은 운영 환경에서 설정
    
    class Config:
        env_file = ".env"

settings = Settings()
