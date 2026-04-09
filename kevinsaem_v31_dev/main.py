# main.py
# FastAPI 앱 진입점
# 라우터 등록, 미들웨어, 정적 파일, 템플릿 설정

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db, close_db
from app.routers import booking_pages, admin_pages, api

app = FastAPI(
    title="케빈샘 AI코딩 - 예약 시스템",
    version="3.1",
    docs_url="/api/docs",  # Swagger UI
    redoc_url=None,
)

# CORS 설정 (Flutter Web 등 외부 도메인 허용 시)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 라우터 등록
app.include_router(booking_pages.router)  # 수강생 웹: /booking/*
app.include_router(admin_pages.router)    # 관리자 웹: /admin/*
app.include_router(api.router)            # JSON API: /api/v1/*

# 앱 시작/종료 시 DB 연결 관리
@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    await close_db()

# 헬스체크
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "3.1"}
