# 보안 감사 보고서 (Security Audit Report)

**프로젝트:** kevinsaem-booking (케빈샘 AI코딩 예약 시스템)
**감사일:** 2026-03-23
**감사자:** Security Agent (Claude)
**버전:** v3.1

---

## 요약 (Executive Summary)

전체 코드베이스를 분석한 결과, 배포 전 반드시 수정해야 할 **CRITICAL 이슈 5건**, 권장 수정 **MEDIUM 이슈 6건**, 개선 권장 **LOW 이슈 4건**을 발견했습니다.

가장 심각한 문제는 **JWT 시크릿 키가 약한 기본값**으로 설정되어 있는 점, **로그인 브루트포스 방어가 없는 점**, **쿠키에 secure 플래그가 없는 점**입니다.

SQL Injection은 모든 쿼리가 파라미터화되어 있어 안전합니다. XSS도 Jinja2 자동 이스케이프가 적용되어 기본적으로 안전합니다.

---

## A. 인증 & 세션 (Authentication & Session)

### CRITICAL-01: JWT 시크릿 키 기본값이 약함
- **위치:** `app/config.py:20`, `.env:5`
- **현황:** `JWT_SECRET`의 기본값이 `"change-this-to-random-secret-key"`이고, `.env`에서도 `"dev-secret-key-not-for-production-1234567890abcdef"`로 설정됨
- **위험:** 프로덕션에서 이 값이 그대로 사용되면 공격자가 JWT를 위조하여 아무 사용자로 로그인 가능
- **수정 방안:**
  1. 프로덕션 `.env`에 최소 32바이트 이상의 랜덤 시크릿 설정: `python -c "import secrets; print(secrets.token_hex(32))"`
  2. `config.py`에서 프로덕션 모드일 때 기본값 사용 시 서버 시작 차단 로직 추가

### CRITICAL-02: 로그인 브루트포스 방어 없음 (Rate Limiting)
- **위치:** `app/routers/booking_pages.py:62-74` (`/booking/login` POST)
- **현황:** 로그인 시도 횟수 제한 없음. 인증번호가 4자리 숫자(0000~9999)라 10,000번 시도로 100% 돌파 가능
- **위험:** 자동화된 브루트포스 공격으로 모든 사용자 계정 탈취 가능
- **수정 방안:**
  1. IP 기반 + 계정 기반 rate limiting 추가 (예: `slowapi` 라이브러리)
  2. 5회 실패 시 해당 계정 15분 잠금
  3. 인증번호를 6자리로 확장 고려

### CRITICAL-03: 쿠키에 `secure` 플래그 미설정
- **위치:** `app/routers/booking_pages.py:73`
- **현황:** `response.set_cookie("token", token, httponly=True, samesite="lax", max_age=1800)` - `secure=True` 없음
- **위험:** HTTP 연결에서 토큰이 평문으로 전송되어 중간자 공격(MITM)으로 세션 탈취 가능
- **수정 방안:**
  ```python
  response.set_cookie(
      "token", token,
      httponly=True,
      secure=True,  # HTTPS 전용
      samesite="lax",
      max_age=1800
  )
  ```
  - 개발 환경에서는 `secure=settings.DB_MODE == "production"` 으로 분기 가능

### MEDIUM-01: 인증번호 생성에 `random` 모듈 사용 (암호학적으로 안전하지 않음)
- **위치:** `app/services/auth_service.py:100-103`
- **현황:** `random.randint(1000, 9999)` 사용 - 예측 가능한 난수
- **수정 방안:** `secrets.randbelow(9000) + 1000` 사용

### MEDIUM-02: HTMX partial 엔드포인트에 인증 체크 미흡
- **위치:** `app/routers/booking_pages.py:233-261`
- **현황:** `calendar_grid_partial`, `time_slots_partial`, `teacher_list_partial`에서 `user=Depends(get_current_user)` 를 받지만 `if not user:` 체크가 없음. 인증 없이 스케줄 데이터 조회 가능
- **수정 방안:** 각 partial 핸들러에 `if not user: return HTMLResponse("", status_code=401)` 추가

### LOW-01: JWT 만료 시간 불일치
- **위치:** `app/config.py:21` vs `.env:6` vs `booking_pages.py:73`
- **현황:** config 기본값 30분, .env에서 60분, 쿠키 max_age는 1800초(30분). JWT는 60분 유효하지만 쿠키는 30분에 만료됨
- **수정 방안:** 쿠키 max_age와 JWT_EXPIRE_MINUTES를 동기화: `max_age=settings.JWT_EXPIRE_MINUTES * 60`

---

## B. 인젝션 (Injection)

### SQL Injection: 안전
- **결과:** 모든 `execute_query()` 호출이 `?` 파라미터 바인딩 사용. 문자열 보간(f-string, format)으로 SQL을 조립하는 곳 없음
- `auth_service.py`: 3개 쿼리 - 모두 파라미터화
- `booking_service.py`: 5개 쿼리 - 모두 파라미터화
- `schedule_service.py`: 4개 쿼리 - 모두 파라미터화
- `booking_pages.py` 내 직접 쿼리: 모두 파라미터화

### XSS: 기본적으로 안전
- **결과:** Jinja2 기본 auto-escape 활성화. `|safe` 필터나 `{% autoescape false %}` 사용 없음
- 모든 `{{ variable }}` 출력이 자동 이스케이프됨

### MEDIUM-03: CSRF 보호 없음
- **위치:** 모든 POST 엔드포인트
- **현황:** CSRF 토큰 없음. 쿠키 기반 인증 + POST 폼 사용 시 CSRF 공격 가능
- **위험:** 악의적 사이트가 사용자 대신 예약 생성/취소 가능
- **수정 방안:**
  1. `SameSite=lax`가 일부 방어하지만 완전하지 않음
  2. `starlette-csrf` 또는 커스텀 CSRF 미들웨어 추가
  3. 또는 HTMX 요청에 커스텀 헤더(`X-Requested-With`) 검증

### Path Traversal: 해당 없음
- 파일 업로드/다운로드 기능 없음

---

## C. 민감 데이터 (Sensitive Data)

### .gitignore 상태: 양호
- `.env` ✅ 포함
- `credentials.json` ✅ 포함
- `token.json` ✅ 포함
- `.ftp_config.json` ✅ 포함
- `dev.db` ✅ 포함

### MEDIUM-04: 하드코딩된 인증번호 (시드 데이터)
- **위치:** `app/seed.py:170-175`
- **현황:** 테스트 계정의 인증번호가 하드코딩됨 (1234, 5678, 9012, 3456, 7890)
- **위험:** 개발 모드 전용이지만, 프로덕션에서 실수로 시드가 실행되면 이 인증번호로 로그인 가능
- **수정 방안:** 시드 함수에 `assert DB_MODE == "development"` 가드 추가

### CRITICAL-04: dev.db 파일이 웹에서 접근 가능할 수 있음
- **위치:** `main.py:29` - `app.mount("/static", StaticFiles(directory="static"), name="static")`
- **현황:** `/static` 마운트는 `static/` 폴더만 서빙하므로 직접적으로 dev.db는 노출되지 않음. 하지만 `dev.db`가 프로젝트 루트에 위치
- **위험:** 웹서버(Nginx/Apache) 설정이 잘못되면 dev.db가 노출될 수 있음
- **수정 방안:** 프로덕션 배포 시 dev.db가 포함되지 않도록 확인. 리버스 프록시에서 `.db` 파일 접근 차단

### LOW-02: 에러 메시지에 시스템 정보 노출 가능
- **위치:** `app/services/booking_service.py:108`
- **현황:** `return {"success": False, "message": str(e)}` - 예외 메시지가 그대로 사용자에게 전달됨
- **수정 방안:** 사용자에게는 일반적 메시지, 로그에 상세 에러 기록

---

## D. API 보안

### MEDIUM-05: CORS `allow_methods=["*"]`, `allow_headers=["*"]`
- **위치:** `main.py:20-26`
- **현황:** `allow_origins`는 제한적이지만 methods와 headers가 와일드카드
- **수정 방안:** 필요한 메서드/헤더만 명시 - `allow_methods=["GET", "POST"]`, `allow_headers=["Content-Type", "HX-Request"]`

### CRITICAL-05: 전체 엔드포인트에 Rate Limiting 없음
- **위치:** 전체 라우터
- **현황:** 어떤 엔드포인트에도 요청 속도 제한 없음
- **위험:** DDoS, 브루트포스, 스크래핑에 취약
- **수정 방안:** `slowapi` 라이브러리로 글로벌 rate limiting 추가 (예: IP당 분당 60회)

### MEDIUM-06: API 문서가 프로덕션에서 노출됨
- **위치:** `main.py:15`
- **현황:** `docs_url="/api/docs"` - Swagger UI가 항상 노출
- **수정 방안:** 프로덕션에서 비활성화: `docs_url="/api/docs" if settings.DB_MODE == "development" else None`

---

## E. HTTP 보안 헤더

### MEDIUM-07: 보안 헤더 미설정
- **위치:** `main.py`, `templates/base.html`
- **현황:** 다음 헤더가 모두 미설정
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy`
  - `Strict-Transport-Security`
  - `X-XSS-Protection`
- **수정 방안:** FastAPI 미들웨어로 추가:
  ```python
  @app.middleware("http")
  async def add_security_headers(request, call_next):
      response = await call_next(request)
      response.headers["X-Content-Type-Options"] = "nosniff"
      response.headers["X-Frame-Options"] = "DENY"
      response.headers["X-XSS-Protection"] = "1; mode=block"
      response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
      return response
  ```

---

## F. 의존성 (Dependencies)

### LOW-03: python-jose 라이브러리 유지보수 중단 우려
- **위치:** `requirements.txt:22`
- **현황:** `python-jose==3.3.0` - 이 라이브러리는 업데이트가 느리고 CVE가 보고된 적 있음
- **수정 방안:** `PyJWT`로 교체 고려 (더 활발히 관리됨)

### LOW-04: CDN 의존성의 무결성 검증 없음
- **위치:** `templates/base.html:15,24,27`
- **현황:** Tailwind CSS, HTMX, Alpine.js를 CDN에서 로드하면서 `integrity` 속성 없음
- **위험:** CDN이 해킹되면 악성 스크립트 주입 가능
- **수정 방안:** SRI(Subresource Integrity) 해시 추가 또는 로컬 번들 사용

---

## G. 코드별 세부 점검

### cancel_booking: 사용자 소유권 확인 — 안전
- **위치:** `app/services/booking_service.py:117-123`
- **결과:** `WHERE idx = ? AND mem_mbrid = ?` 조건으로 본인 예약만 취소 가능. 타 사용자 예약 취소 불가

### 채팅 메시지 접근 제어 — 안전
- **위치:** `app/routers/booking_pages.py:428-485`
- **결과:** 채팅 조회 시 `WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)` 조건으로 본인이 참여한 대화만 조회. 읽음 처리도 본인 수신 메시지만 대상

### 타 사용자 데이터 접근 — 안전
- **결과:** 모든 데이터 조회에서 `user["mem_MbrId"]` 기반 필터링 적용. settle_code 기반 조회도 JWT에서 추출한 값 사용

### 채팅 메시지 전송 엔드포인트 — 미구현
- **위치:** `templates/booking/chat.html:61` - `hx-post="/booking/chat/{{ teacher_id }}/send"` 참조
- **현황:** 이 엔드포인트가 라우터에 정의되지 않음. 현재는 404 반환될 것
- **참고:** 구현 시 sender_id를 JWT에서 추출하도록 해야 함 (Form에서 받으면 위조 가능)

### 채팅 폴링 엔드포인트 — 미구현
- **위치:** `templates/booking/chat.html:26-28` - `hx-get="/booking/chat/{{ teacher_id }}/messages"` 참조
- **현황:** 이 엔드포인트도 라우터에 정의되지 않음

---

## 발견 사항 요약표

| # | 등급 | 항목 | 위치 |
|---|------|------|------|
| CRITICAL-01 | CRITICAL | JWT 시크릿 키 약한 기본값 | config.py, .env |
| CRITICAL-02 | CRITICAL | 로그인 브루트포스 방어 없음 | booking_pages.py:62 |
| CRITICAL-03 | CRITICAL | 쿠키 secure 플래그 미설정 | booking_pages.py:73 |
| CRITICAL-04 | CRITICAL | dev.db 웹 노출 가능성 | 프로젝트 루트 |
| CRITICAL-05 | CRITICAL | 전체 Rate Limiting 없음 | 전체 라우터 |
| MEDIUM-01 | MEDIUM | 인증번호 생성 약한 난수 | auth_service.py:102 |
| MEDIUM-02 | MEDIUM | HTMX partial 인증 체크 누락 | booking_pages.py:233-261 |
| MEDIUM-03 | MEDIUM | CSRF 보호 없음 | 모든 POST 폼 |
| MEDIUM-04 | MEDIUM | 시드 데이터 하드코딩 인증번호 | seed.py:170 |
| MEDIUM-05 | MEDIUM | CORS 와일드카드 methods/headers | main.py:24-25 |
| MEDIUM-06 | MEDIUM | Swagger UI 프로덕션 노출 | main.py:15 |
| MEDIUM-07 | MEDIUM | 보안 헤더 미설정 | main.py |
| LOW-01 | LOW | JWT/쿠키 만료 시간 불일치 | config.py, booking_pages.py |
| LOW-02 | LOW | 에러 메시지 시스템 정보 노출 | booking_service.py:108 |
| LOW-03 | LOW | python-jose 유지보수 우려 | requirements.txt |
| LOW-04 | LOW | CDN SRI 해시 미적용 | base.html |

---

## 우선순위별 수정 권장 순서

### 1단계: 배포 전 반드시 (CRITICAL)
1. JWT 시크릿 키를 강력한 랜덤 값으로 변경
2. 로그인 rate limiting 추가 (slowapi)
3. 쿠키에 `secure=True` 추가
4. 전역 rate limiting 미들웨어 추가
5. 프로덕션 배포 시 dev.db 제외 확인

### 2단계: 가급적 빨리 (MEDIUM)
1. CSRF 보호 추가
2. 보안 헤더 미들웨어 추가
3. HTMX partial 인증 체크 추가
4. Swagger UI 프로덕션 비활성화
5. CORS 설정 최소화
6. 인증번호 생성에 secrets 모듈 사용

### 3단계: 개선 권장 (LOW)
1. JWT/쿠키 만료 시간 동기화
2. 에러 메시지 정리
3. python-jose → PyJWT 교체 검토
4. CDN SRI 해시 추가
