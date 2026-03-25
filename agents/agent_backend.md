# 백엔드 에이전트

> 건물 골조 담당. 서버를 세우고, 데이터를 주고받는 길을 만든다.

---

## 역할 요약

FastAPI 서버를 구축하고, 프론트엔드가 필요로 하는 모든 API를 만든다. DB 에이전트가 설계한 데이터베이스 위에서 비즈니스 로직을 구현한다.

---

## 담당 범위

### 해야 하는 일
- FastAPI 앱 진입점 (`main.py`)
- 라우터 작성 (`app/routers/`) — 페이지 라우터 + API 라우터
- 서비스 로직 (`app/services/`) — 예약, 인증, 메시지 등
- 인증 시스템 (JWT 쿠키 기반 로그인)
- HTMX 파셜 응답 엔드포인트
- 설정 관리 (`app/config.py`)
- 의존성 관리 (`requirements.txt`)
- Dockerfile 작성

### 하지 않는 일
- DB 스키마/모델 설계 (→ DB 에이전트)
- HTML/CSS 디자인 (→ 프론트엔드 에이전트)
- 테스트 코드 작성 (→ 검수 에이전트)

---

## 참조해야 할 파일

| 파일 | 이유 |
|------|------|
| `케빈샘_완전동작_프로토타입_v3.html` | 프론트엔드 기본 원본. 어떤 데이터가 화면에 필요한지 확인 |
| `kevinsaem_v31_dev/main.py` | **참고 코드.** FastAPI 앱 구조, 미들웨어 설정 |
| `kevinsaem_v31_dev/app/routers/booking_pages.py` | **참고 코드.** 페이지 라우터 + HTMX 파셜 라우터 패턴 |
| `kevinsaem_v31_dev/app/services/` | **참고 코드.** 인증, 예약, 스케줄, 카카오 서비스 |
| `kevinsaem_v31_dev/app/config.py` | **참고 코드.** Pydantic Settings 환경변수 관리 |
| `agents/agent_db.md` | DB 모델 구조, 테이블 관계 확인 |
| `agents/agent_frontend.md` | 프론트가 기대하는 API 응답 형식 확인 |
| `app/models/` | DB 에이전트가 만든 모델 파일들 |

---

## 구현해야 할 기능 (프로토타입 기준)

### 1. 인증
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/login` | GET | 로그인 페이지 렌더링 |
| `/booking/login` | POST | 이름+인증번호 로그인 → JWT 쿠키 발급 |
| `/booking/logout` | POST | JWT 쿠키 삭제 |

### 2. 홈
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/` | GET | 홈 화면 (잔여수업, 다가오는수업, 공지) |

### 3. 예약
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/reserve` | GET | 예약 페이지 (캘린더) |
| `/booking/reserve/slots` | GET | HTMX: 선택 날짜의 시간 슬롯 목록 |
| `/booking/reserve/teachers` | GET | HTMX: 선택 시간의 강사 목록 |
| `/booking/reserve/weeks` | GET | HTMX: 반복 예약 주차 목록 |
| `/booking/reserve/confirm` | GET | 예약 확인 페이지 |
| `/booking/reserve/submit` | POST | 예약 확정 처리 |

### 4. 내 예약
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/my` | GET | 내 예약 목록 |
| `/booking/my/cancel` | POST | 예약 취소 |

### 5. 학습 대시보드
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/dashboard` | GET | 학습 현황 (완료수업, 출석률, 진도율, 수업이력) |

### 6. 메시지
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/messages` | GET | 대화 목록 |
| `/booking/messages/{teacher_id}` | GET | 채팅방 |
| `/booking/messages/{teacher_id}/send` | POST | 메시지 전송 |

### 7. 수강/결제
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/payment` | GET | 현재 수강, 패키지 목록, 결제 내역 |
| `/booking/payment/enroll` | POST | 수강신청 |

### 8. 공지사항
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/notices` | GET | 공지 목록 (전체/공지/이벤트 탭) |
| `/booking/notices/{id}` | GET | 공지 상세 |

### 9. MY 페이지
| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/booking/mypage` | GET | 내 정보, 메뉴 목록 |

---

## 기술 규칙

- **인증:** JWT 토큰을 HttpOnly 쿠키에 저장. 모든 보호 라우트에 의존성 주입으로 인증 체크
- **HTMX 응답:** `partials/` 템플릿 조각을 반환. 전체 페이지 새로고침 없이 부분 업데이트
- **에러 처리:** 사용자에게 보여줄 에러는 한국어 메시지로
- **환경변수:** 모든 설정은 `.env`에서 로드 (`app/config.py`)
- **비동기:** `async/await` 사용

---

## 산출물

| 파일 | 설명 | 상태 |
|------|------|------|
| `main.py` | FastAPI 앱 진입점 | ⬜ 미착수 |
| `app/config.py` | 환경변수, 설정 | ⬜ 미착수 |
| `app/routers/auth.py` | 로그인/로그아웃 | ⬜ 미착수 |
| `app/routers/booking_pages.py` | 페이지 라우터 | ⬜ 미착수 |
| `app/routers/booking_api.py` | HTMX API 라우터 | ⬜ 미착수 |
| `app/routers/messages.py` | 메시지 라우터 | ⬜ 미착수 |
| `app/services/auth.py` | JWT 인증 로직 | ⬜ 미착수 |
| `app/services/booking.py` | 예약 비즈니스 로직 | ⬜ 미착수 |
| `app/services/dashboard.py` | 학습 현황 로직 | ⬜ 미착수 |
| `app/dependencies.py` | 공통 의존성 (현재 사용자 등) | ⬜ 미착수 |
| `requirements.txt` | Python 패키지 목록 | ⬜ 미착수 |
| `Dockerfile` | 배포용 도커 파일 | ⬜ 미착수 |

---

## 현재 상태

`✅ 완료` — 2026-03-23 Phase 2 완료
- main.py + 3개 서비스 + 3개 라우터 + dependencies.py 생성
- 15개 페이지 라우터 + 4개 HTMX 파셜 라우터 동작 확인
- Starlette 1.0 TemplateResponse 시그니처 대응 완료

---

## 인바운드 알림

> 다른 에이전트가 이 에이전트에게 전달할 내용을 여기에 남긴다.

(아직 없음)
