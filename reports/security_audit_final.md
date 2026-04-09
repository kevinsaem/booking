# 보안 감사 최종 보고서

**프로젝트:** kevinsaem-booking
**감사일:** 2026-03-24
**감사 범위:** 전체 소스코드 (main.py, routers, services, database, templates, static, .env, .gitignore)

---

## 요약

| 등급 | 건수 |
|------|------|
| CRITICAL | 5 |
| MEDIUM | 8 |
| LOW | 5 |

---

## A. 인증 & 세션

### CRITICAL-A1: 로그인에 Rate Limiting 없음
- **위치:** `app/routers/booking_pages.py` (`/booking/login` POST)
- **문제:** 이름+인증번호(4자리) 로그인에 속도 제한이 없다. 인증번호가 4자리 숫자(0000~9999)이므로, 자동화 도구로 최대 10,000번 시도하면 모든 사용자 계정에 접근 가능하다.
- **영향:** 무차별 대입 공격(Brute Force)으로 아무 사용자 계정이든 탈취 가능.
- **수정 방안:** `slowapi` 또는 커스텀 미들웨어로 IP 당 로그인 시도 횟수 제한 (예: 5회/분). 일정 실패 후 계정 잠금 또는 CAPTCHA 추가.

### CRITICAL-A2: 인증번호가 MD5 해시 기반의 예측 가능한 값
- **위치:** `app/routers/auth.py` 113행
- **문제:** 신규 가입 시 비밀번호를 `MD5(전화번호 뒤 4자리)`로 설정한다. 전화번호가 없으면 `MD5("0000")`이 된다. 이 값이 `mem_Pwd`에 저장되지만, 로그인에는 `injeung_code`가 사용된다. 다만 MD5는 약한 해시이고, 이 패턴은 예측 가능하다.
- **영향:** 비밀번호 해시가 쉽게 역추적 가능.
- **수정 방안:** bcrypt 등 강한 해시 사용. 인증번호는 암호학적 랜덤 생성 (현재 `generate_auth_code()`는 `secrets` 사용으로 적절하나, 실제 가입 시 이 함수가 아닌 MD5 패턴 사용).

### MEDIUM-A3: JWT에 settle_code 포함 (클라이언트 변조 가능성)
- **위치:** `app/services/auth_service.py` 13~20행, `app/routers/booking_pages.py` 260행
- **문제:** JWT 토큰에 `settle_code`가 포함된다. JWT 자체는 서명되어 변조 불가하지만, `/booking/complete` POST에서 form의 `settle_code`를 `int(form.get("settle_code"))`로 직접 받아 사용한다. 공격자가 다른 사람의 settle_code를 form에 넣으면 다른 사람의 수강권으로 예약 가능.
- **수정 방안:** form에서 받은 settle_code 대신, 반드시 JWT의 `user["settle_code"]`를 사용.

### LOW-A4: JWT 만료와 쿠키 max_age 정렬됨
- **위치:** `app/routers/auth.py` 155행, `app/services/auth_service.py` 18행
- **결과:** 쿠키 `max_age=JWT_EXPIRE_MINUTES*60`, JWT `exp=JWT_EXPIRE_MINUTES`로 일치. **문제 없음.**

### LOW-A5: 쿠키 보안 속성 적절함
- **위치:** `app/routers/auth.py` 150~156행
- **결과:** `httponly=True`, `secure=is_prod`, `samesite="lax"` 설정됨. **문제 없음.**

---

## B. SQL Injection

### MEDIUM-B1: schedule_service.py에서 f-string SQL 빌딩
- **위치:** `app/services/schedule_service.py` 37, 40행
- **문제:** `_teacher_filter()` 함수에서 `MENTOR_1ON1_TYPE`과 `MENTOR_VIRTUAL_TYPE` 상수를 f-string으로 SQL에 삽입한다. 현재는 하드코딩된 상수(`'4'`, `'5'`)라 실질적 위험은 낮지만, SQL 인젝션 방어의 모범 사례에 어긋난다.
- **수정 방안:** 파라미터 바인딩으로 변경.

### MEDIUM-B2: admin_pages.py의 동적 WHERE 절 구성
- **위치:** `app/routers/admin_pages.py` 369~379행
- **문제:** `admin_bookings()`에서 `f"...{where}..."` 형태로 SQL을 동적 구성한다. `where` 절의 조건들은 `?` 파라미터를 사용하고 있어 실질적인 SQL 인젝션 위험은 없지만, f-string으로 쿼리를 조합하는 패턴은 유지보수 시 실수 유발 가능.
- **수정 방안:** 안전하지만 코드 리뷰 시 주의 필요. 가능하면 ORM이나 쿼리 빌더 활용.

### B3: 전체 execute_query 호출 점검 결과
- **결과:** 모든 `execute_query()` 호출이 `?` 파라미터 바인딩을 사용한다. 사용자 입력이 직접 SQL 문자열에 삽입되는 곳은 발견되지 않음. **대체로 안전.**

---

## C. XSS (Cross-Site Scripting)

### LOW-C1: Jinja2 auto-escape 활성화됨
- **위치:** Starlette의 `Jinja2Templates` (자동으로 `select_autoescape()` 적용)
- **결과:** `.html` 확장자에 대해 auto-escape가 기본 활성화됨. `|safe` 필터 사용 없음. `{% autoescape false %}` 사용 없음. **문제 없음.**

### MEDIUM-C2: HTMLResponse에 직접 HTML 문자열 구성
- **위치:** `app/routers/teacher_pages.py` 578~583행, `app/routers/booking_pages.py` 522~526행
- **문제:** `save_memo()`에서 HTML 문자열을 직접 구성해 반환한다. 여기에는 사용자 입력이 포함되지 않아 현재는 안전하지만, 나중에 동적 데이터가 추가되면 XSS 위험이 생긴다. `rate_mentor()`의 별점 HTML도 마찬가지.
- **수정 방안:** partial 템플릿으로 분리하여 항상 auto-escape 적용.

---

## D. CSRF

### MEDIUM-D1: POST 폼에 CSRF 토큰 없음
- **위치:** 모든 POST 폼 (`/booking/login`, `/booking/complete`, `/booking/cancel/*`, `/teacher/schedule/add`, `/admin/notices/create` 등)
- **문제:** `SameSite=Lax` 쿠키가 크로스사이트 POST를 차단하므로 대부분의 CSRF 공격은 방어되지만, 같은 사이트 내 서브도메인에서의 공격이나 일부 엣지 케이스는 방어되지 않는다.
- **수정 방안:** `fastapi-csrf-protect` 등의 CSRF 토큰 미들웨어 추가 권장.

### LOW-D2: 상태 변경 GET 요청 없음
- **결과:** 모든 상태 변경(예약, 취소, 메시지 전송 등)이 POST로 처리됨. **문제 없음.**

---

## E. 민감 데이터

### LOW-E1: .env가 .gitignore에 포함됨
- **위치:** `.gitignore` 2행
- **결과:** `.env`, `credentials.json`, `token.json`, `.ftp_config.json`, `dev.db` 모두 gitignore 처리됨. **문제 없음.**

### MEDIUM-E2: .env에 카카오 REST API 키와 토스 테스트 키 포함
- **위치:** `.env` 17~22행
- **문제:** 카카오 REST API 키(`4c94845b...`)가 .env에 하드코딩되어 있다. 이것은 테스트 키이지만, production 배포 시 반드시 환경변수로 교체해야 한다. 토스 키도 `test_` 접두사이므로 테스트 키임이 확인됨.
- **참고:** .env가 gitignore에 있으므로 Git에 유출 위험은 없음. 다만 .env 파일이 서버에서 적절히 보호되는지 확인 필요.

### MEDIUM-E3: config.py의 기본값에 약한 비밀번호
- **위치:** `app/config.py` 20행, 36행
- **문제:**
  - `JWT_SECRET` 기본값: `"change-this-to-random-secret-key"`
  - `ADMIN_PASSWORD` 기본값: `"admin1234"`
  - production에서 `JWT_SECRET`은 `main.py`에서 검증하지만, `ADMIN_PASSWORD`는 검증 없음.
- **수정 방안:** production 모드에서 `ADMIN_PASSWORD`도 기본값 체크 추가. 참고로 현재 admin 인증은 카카오 로그인 + role 기반이므로 `ADMIN_PASSWORD`가 실제 사용되는지 확인 필요.

### LOW-E4: dev.db 접근 불가 확인
- **위치:** `main.py` 54행 (static 마운트 경로: `/static` → `static/` 디렉토리)
- **결과:** `dev.db`는 프로젝트 루트에 있고, static 파일 서빙은 `static/` 디렉토리에 한정. URL로 직접 접근 불가. **문제 없음.**

---

## F. 입력 검증

### MEDIUM-F1: Form 파라미터 타입 검증 미흡
- **위치:** `app/routers/booking_pages.py` 258행, 260행
- **문제:** `/booking/complete`에서 `int(form.get("room_idx"))`, `int(form.get("settle_code"))`를 직접 변환한다. 악의적 입력 시 ValueError 발생하여 500 에러 반환.
- **수정 방안:** `Form(...)` 파라미터를 사용하여 FastAPI 자체 검증 활용. 또는 try-except로 안전한 변환.

### MEDIUM-F2: teacher_pages.py의 repeat_weeks 검증 없음
- **위치:** `app/routers/teacher_pages.py` 200행
- **문제:** `repeat_weeks: int = Form(1)` - 음수나 매우 큰 값이 들어오면 비정상 동작 가능 (수천 개 슬롯 생성 시도).
- **수정 방안:** `1 <= repeat_weeks <= 12` 범위 검증 추가.

### F3: 파일 업로드 없음
- **결과:** 파일 업로드 기능 없음. **해당 없음.**

---

## G. 비즈니스 로직

### CRITICAL-G1: 다른 사람의 settle_code로 예약 가능
- **위치:** `app/routers/booking_pages.py` 250~268행
- **문제:** `/booking/complete` POST에서 `settle_code`를 form 데이터에서 직접 받는다. 공격자가 브라우저 개발자도구로 form의 `settle_code` hidden input을 다른 사람의 값으로 변경하면, 해당 수강권의 잔여 횟수를 차감하면서 예약이 가능하다.
- **수정 방안:** `settle_code`는 JWT의 `user["settle_code"]`에서만 가져오도록 수정.

### CRITICAL-G2: 연구노트 저장 시 lecturede_idx 소유권 미검증
- **위치:** `app/routers/booking_pages.py` 529~560행
- **문제:** `/booking/dashboard/save-note`에서 `lecturede_idx`를 form으로 받아 해당 레코드의 `report`를 업데이트한다. 해당 `lecturede_idx`가 현재 사용자의 것인지 확인하지 않는다. 다른 학생의 연구노트를 덮어쓸 수 있다.
- **수정 방안:** UPDATE 쿼리에 `AND student_id = ?` 조건 추가하여 본인의 레코드만 수정 가능하게.

### MEDIUM-G3: 잔여 횟수 음수 방지 확인
- **위치:** `app/services/booking_service.py` 71행, 105~106행
- **결과:** `get_remaining()`은 `max(row["remaining"], 0)`으로 음수 방지. `create_booking()`은 `remaining < len(dates)` 체크. **대체로 안전.** 다만 동시 요청(Race Condition) 시 음수 가능성 있음. DB 레벨 잠금 권장.

### LOW-G4: 예약 취소 시 본인 확인
- **위치:** `app/services/booking_service.py` 176~185행
- **결과:** `cancel_booking(idx, mem_id)`에서 `WHERE idx = ? AND mem_mbrid = ?`로 본인 확인. **문제 없음.**

### LOW-G5: 메시지 전송 시 발신자 확인
- **위치:** `app/routers/booking_pages.py` 707~723행, `app/routers/teacher_pages.py` 483~498행
- **결과:** 메시지 발신자(`sender_id`)는 항상 JWT의 `user["mem_MbrId"]`에서 가져옴. 다른 사람으로 위장 불가. **문제 없음.**

---

## H. 결제 보안

### CRITICAL-H1: 결제 금액으로 패키지 매칭 (금액 변조 가능)
- **위치:** `app/routers/payment.py` 66~76행
- **문제:** 결제 성공 후 `amount`(결제 금액)으로 패키지를 DB에서 조회한다 (`WHERE price = ?`). 문제점:
  1. 같은 가격의 패키지가 2개 이상이면 잘못된 패키지가 선택될 수 있음
  2. 토스 결제 위젯에서 금액이 변조되어 더 저렴한 가격으로 비싼 패키지를 구매할 가능성
  3. `orderId`에 `package_code`를 포함시키지 않아 패키지-금액 정합성 검증 불가
- **수정 방안:**
  - `orderId`에 `package_code`를 포함 (예: `ORDER-20260324-XXXXX-PKG3`)
  - 결제 승인 전에 `orderId`에서 `package_code`를 파싱하여 DB의 패키지 가격과 `amount`가 일치하는지 서버에서 검증
  - 또는 결제 시작 시 서버에 주문 정보를 저장하고, 성공 콜백에서 저장된 정보와 대조

### MEDIUM-H2: 이중 결제 방지 없음
- **위치:** `app/services/payment_service.py`, `app/routers/payment.py`
- **문제:** 동일 `orderId`로 이중 승인 시도를 방지하는 로직이 없다. 토스 API 자체가 중복 승인을 거부하지만, 서버 측에서도 orderId 사용 여부를 기록하여 이중 수강권 생성을 방지해야 한다.
- **수정 방안:** 결제 성공 시 `orderId`를 DB에 저장하고, 중복 요청 시 기존 결과 반환.

---

## I. API 보안

### I1: CORS 설정 적절
- **위치:** `main.py` 31~37행
- **결과:** `allow_origins`가 설정 파일에서 가져오며, `allow_methods`는 `["GET", "POST"]`만 허용. `allow_headers=["*"]`은 약간 넓지만 credentials와 함께 사용 시 브라우저가 자동으로 제한. **대체로 안전.**

### I2: 보안 헤더 적절
- **위치:** `main.py` 41~50행
- **결과:** `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, HSTS(production) 모두 설정됨. **문제 없음.**
- **개선 가능:** `Content-Security-Policy` 헤더 추가 권장.

### I3: Rate Limiting 전역 미적용
- **문제:** 로그인뿐 아니라 전체 API에 Rate Limiting이 없다. DDoS 또는 스크래핑에 취약.
- **수정 방안:** `slowapi` 라이브러리로 전역 또는 엔드포인트별 Rate Limiting 추가.

---

## J. 인프라

### J1: Production에서 Swagger UI 비활성화
- **위치:** `main.py` 21~27행
- **결과:** `is_prod`일 때 `docs_url=None`. **문제 없음.**

### J2: Production JWT 시크릿 검증
- **위치:** `main.py` 14~18행
- **결과:** production 모드에서 `"not-for-production"` 포함 시 시작 거부. 다만 `.env`의 기본 `JWT_SECRET`인 `"dev-secret-key-not-for-production-1234567890abcdef"`와 `config.py`의 기본값 `"change-this-to-random-secret-key"`은 패턴이 다르다. `config.py` 기본값에는 `"not-for-production"`이 없으므로, `.env` 없이 production 실행 시 약한 기본 키가 사용될 수 있다.
- **수정 방안:** production 검증에서 `config.py`의 기본값(`"change-this-to-random-secret-key"`)도 체크.

### J3: Static 파일 민감 정보 없음
- **위치:** `static/js/booking.js`
- **결과:** API 키나 비밀 정보 없음. **문제 없음.**

---

## 수정 우선순위

### 즉시 수정 (배포 전 필수)

| # | 등급 | 항목 | 요약 |
|---|------|------|------|
| 1 | CRITICAL | A1 | 로그인 Rate Limiting 추가 (4자리 인증번호 브루트포스 방지) |
| 2 | CRITICAL | G1 | `/booking/complete`에서 settle_code를 form이 아닌 JWT에서 가져오기 |
| 3 | CRITICAL | H1 | 결제 시 패키지 코드+금액 서버 검증 (금액만으로 패키지 매칭하지 않기) |
| 4 | CRITICAL | G2 | 연구노트 저장 시 lecturede_idx 소유권 검증 추가 |
| 5 | CRITICAL | A2 | 신규가입 비밀번호를 MD5(전화번호4자리) 대신 강한 해시 사용 |

### 조속히 수정

| # | 등급 | 항목 | 요약 |
|---|------|------|------|
| 6 | MEDIUM | A3 | confirm 페이지의 settle_code를 JWT에서 가져오기 |
| 7 | MEDIUM | D1 | CSRF 토큰 미들웨어 추가 |
| 8 | MEDIUM | E3 | production에서 ADMIN_PASSWORD 기본값 체크 |
| 9 | MEDIUM | F1 | form.get() 직접 int 변환 대신 안전한 검증 |
| 10 | MEDIUM | F2 | repeat_weeks 범위 검증 (1~12) |
| 11 | MEDIUM | H2 | orderId 중복 방지 (이중 수강권 생성 방지) |
| 12 | MEDIUM | B1 | schedule_service의 f-string SQL을 파라미터 바인딩으로 |
| 13 | MEDIUM | C2 | HTMLResponse 직접 구성을 partial 템플릿으로 전환 |

### 개선 권장

| # | 등급 | 항목 | 요약 |
|---|------|------|------|
| 14 | LOW | I2 | Content-Security-Policy 헤더 추가 |
| 15 | LOW | I3 | 전역 Rate Limiting 적용 |
| 16 | LOW | J2 | config.py 기본 JWT_SECRET도 production 검증에 포함 |
| 17 | LOW | G3 | 동시 예약 요청 시 Race Condition 방지 (DB 잠금) |
| 18 | LOW | B2 | admin_bookings의 동적 WHERE 절을 더 명시적으로 |

---

## 안전한 영역 (문제 없음 확인)

- SQL 파라미터 바인딩: 전체적으로 `?` 파라미터 사용 (양호)
- Jinja2 auto-escape: 활성화됨, `|safe` 미사용 (양호)
- 쿠키 보안 속성: HttpOnly, Secure(prod), SameSite=Lax (양호)
- 역할 기반 접근 제어: admin/teacher/student 분리, 각 라우터에서 역할 확인 (양호)
- 예약 취소 소유권 확인: `WHERE idx = ? AND mem_mbrid = ?` (양호)
- 메시지 발신자 위조 불가: JWT에서 가져옴 (양호)
- .gitignore: .env, credentials.json, token.json, dev.db 포함 (양호)
- Swagger UI: production 비활성화 (양호)
- 보안 헤더: 주요 헤더 모두 설정 (양호)
- 별점 소유권 확인: `WHERE R.idx = ? AND R.mem_mbrid = ?` (양호)
- 강사 슬롯 삭제 소유권 확인: `WHERE sch_room_idx = ? AND sch_teach_id = ?` (양호)
