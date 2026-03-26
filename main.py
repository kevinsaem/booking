# main.py
# FastAPI 앱 진입점
# 라우터 등록, 미들웨어, 정적 파일, 보안 헤더

import sys
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZIPMiddleware
from app.config import settings
from app.database import init_db, close_db
from app.routers import booking_pages, admin_pages, api, auth, payment, teacher_pages, message

# 프로덕션 JWT 시크릿 키 검증
if settings.DB_MODE == "production" and "not-for-production" in settings.JWT_SECRET:
    print("❌ 프로덕션 모드에서 개발용 JWT_SECRET을 사용할 수 없습니다.")
    print("   .env 파일에서 JWT_SECRET을 강력한 랜덤 값으로 변경하세요:")
    print('   python -c "import secrets; print(secrets.token_hex(32))"')
    sys.exit(1)

# Swagger UI: 프로덕션에서 비활성화
is_prod = settings.DB_MODE == "production"

app = FastAPI(
    title="케빈샘랩",
    version="3.1",
    docs_url=None if is_prod else "/api/docs",
    redoc_url=None,
)

# GZip 압축 (HTML/CSS/JS 전송 크기 70% 감소)
app.add_middleware(GZIPMiddleware, minimum_size=500)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# 보안 헤더 미들웨어
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # 정적 파일 캐싱
    if "/static/" in str(request.url):
        response.headers["Cache-Control"] = "public, max-age=604800"
    return response


# 정적 파일 (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 라우터 등록
app.include_router(auth.router)              # 카카오 로그인: /auth/*
app.include_router(payment.router)         # 결제 (토스): /booking/payment/*
app.include_router(message.router)        # 메시지: /message/*
app.include_router(booking_pages.router)   # 수강생 웹: /booking/*
app.include_router(teacher_pages.router)  # 강사 포털: /teacher/*
app.include_router(admin_pages.router)     # 관리자 웹: /admin/*
app.include_router(api.router)             # JSON API: /api/v1/*


# 앱 시작/종료 시 DB 연결 관리
@app.on_event("startup")
async def startup():
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


# 템플릿 (1회 초기화)
_templates = Jinja2Templates(directory="templates")


# 루트 → 랜딩 페이지
@app.get("/")
async def root(request: Request):
    return _templates.TemplateResponse(request, "index.html")


# 설문 페이지
@app.get("/survey")
async def survey():
    from fastapi.responses import FileResponse
    return FileResponse("survey.html", media_type="text/html")


# 헬스체크
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "3.1"}
