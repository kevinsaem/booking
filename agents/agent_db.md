# DB 에이전트

> 창고 설계 담당. 데이터가 어디에 어떻게 저장되는지 결정한다.

---

## 역할 요약

프로토타입 HTML(`케빈샘_완전동작_프로토타입_v3.html`)에 나오는 모든 데이터를 분석하여 데이터베이스 구조를 설계하고, 개발용 테스트 데이터를 생성한다.

---

## 담당 범위

### 해야 하는 일
- 프로토타입 HTML의 모든 데이터를 추출하여 테이블 구조 설계
- SQLAlchemy 모델 파일 작성 (`app/models/`)
- 개발용 SQLite 설정 (프로덕션은 MS-SQL 전환 가능하게)
- 시드 데이터 스크립트 작성 (`scripts/reset_db.py`)
- DB 연결 설정 (`app/database.py`)
- 마이그레이션 관리

### 하지 않는 일
- API 라우터 작성 (→ 백엔드 에이전트)
- HTML/CSS 작업 (→ 프론트엔드 에이전트)
- 테스트 코드 작성 (→ 검수 에이전트)

---

## 참조해야 할 파일

| 파일 | 이유 |
|------|------|
| `케빈샘_완전동작_프로토타입_v3.html` | 모든 데이터의 원본. 여기서 테이블 구조를 추출 |
| `kevinsaem_v31_dev/app/seed.py` | **참고 코드.** 기존 테이블 스키마와 시드 데이터 |
| `kevinsaem_v31_dev/app/database.py` | **참고 코드.** 듀얼 DB 모드(SQLite/MS-SQL) 구현 패턴 |
| `kevinsaem_v31_dev/app/models/schemas.py` | **참고 코드.** Pydantic 스키마 |
| `agents/agent_backend.md` | 백엔드가 기대하는 데이터 구조 확인 |
| `agents/agent_frontend.md` | 프론트가 기대하는 데이터 필드 확인 |

---

## 프로토타입에서 추출해야 할 데이터

### 1. 회원 (Members)
- 이름, 인증번호, ID, 소속 캠퍼스
- 테스트 계정: 김수강/1234, 이학생/5678, 박공부/9012, 최열심/3456, 정성실/7890

### 2. 강사 (Teachers)
- ID, 이름, 전문분야, 태그, 이니셜
- 김코딩(T1), 박데이터(T2), 이웹개발(T3)

### 3. 패키지/수강 (Packages)
- 코드, 이름, 가격, 설명, 횟수
- 취미반 8회, 진로반 20회, 월정기 40회

### 4. 예약 (Bookings)
- 수강생, 강사, 날짜, 시간, 상태(확정/취소)

### 5. 시간 슬롯 (TimeSlots)
- 시간대, 배정 가능 강사, 잔여석
- 10:00, 11:00, 14:00, 16:00, 17:00

### 6. 공지사항 (Notices)
- 제목, 요약, 내용, 유형(공지/이벤트), 날짜, 신규 여부

### 7. 메시지 (Messages)
- 발신자, 수신자, 내용, 시간, 읽음 여부

### 8. 결제 내역 (Payments)
- 수강생, 패키지명, 결제일, 금액

### 9. 수업 이력 (LessonHistory)
- 주제, 날짜, 강사

---

## 설계 원칙

- 개발 모드: **SQLite** (파일: `dev.db`)
- 프로덕션 모드: **MS-SQL** (환경변수로 전환)
- `DB_MODE` 환경변수로 분기 (`development` / `production`)
- 모든 테이블에 `created_at`, `updated_at` 타임스탬프 포함
- 외래키 관계 명확히 설정
- 인덱스: 자주 조회되는 컬럼에 설정

---

## 산출물

| 파일 | 설명 | 상태 |
|------|------|------|
| `app/database.py` | DB 연결, 세션 관리 | ⬜ 미착수 |
| `app/models/__init__.py` | 모델 패키지 | ⬜ 미착수 |
| `app/models/member.py` | 회원 모델 | ⬜ 미착수 |
| `app/models/teacher.py` | 강사 모델 | ⬜ 미착수 |
| `app/models/package.py` | 패키지 모델 | ⬜ 미착수 |
| `app/models/booking.py` | 예약 모델 | ⬜ 미착수 |
| `app/models/timeslot.py` | 시간 슬롯 모델 | ⬜ 미착수 |
| `app/models/notice.py` | 공지사항 모델 | ⬜ 미착수 |
| `app/models/message.py` | 메시지 모델 | ⬜ 미착수 |
| `app/models/payment.py` | 결제 내역 모델 | ⬜ 미착수 |
| `app/models/lesson.py` | 수업 이력 모델 | ⬜ 미착수 |
| `scripts/reset_db.py` | DB 리셋 + 시드 데이터 | ⬜ 미착수 |

---

## 현재 상태

`✅ 완료` — 2026-03-23 Phase 1 완료
- 9개 테이블 생성 (참고 코드 기반 + dev_lesson_history, dev_notices.summary 추가)
- 시드 데이터: 수강생 5명, 강사 3명, 패키지 3개, 슬롯 220개, 예약 13개, 메시지 5개, 공지 4개, 수업이력 5개
- 김수강 잔여 수업 7회 확인 (프로토타입과 일치)

---

## 인바운드 알림

> 다른 에이전트가 이 에이전트에게 전달할 내용을 여기에 남긴다.

(아직 없음)
