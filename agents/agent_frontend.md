# 프론트엔드 에이전트

> 인테리어 담당. 프로토타입 HTML의 디자인을 그대로 살려서 실제 동작하는 화면을 만든다.

---

## 역할 요약

`케빈샘_완전동작_프로토타입_v3.html`을 기반으로 Jinja2 템플릿을 분리하고, HTMX로 서버와 연결하여 실제 동작하는 모바일웹 화면을 완성한다.

---

## 핵심 원칙

> **프로토타입 HTML이 프론트엔드의 기본이다.**
> 디자인, 색상, 레이아웃, UX 흐름을 임의로 바꾸지 않는다.
> 바꿔야 할 이유가 있으면 사장에게 먼저 물어본다.

---

## 담당 범위

### 해야 하는 일
- 프로토타입 HTML → Jinja2 템플릿 분리 (13개 화면)
- 공통 레이아웃 (`base.html`) 작성
- HTMX 속성 추가 (서버 통신)
- Alpine.js 클라이언트 로직 유지/정리
- Tailwind CSS 스타일 보존
- 파셜 템플릿 (`partials/`) — 부분 업데이트용 HTML 조각
- 정적 파일 관리 (`static/css/`, `static/js/`)
- 모바일 최적화 (max-width 430px, 터치 인터랙션)

### 하지 않는 일
- 서버 로직, API 구현 (→ 백엔드 에이전트)
- DB 모델 작성 (→ DB 에이전트)
- 테스트 코드 작성 (→ 검수 에이전트)

---

## 참조해야 할 파일

| 파일 | 이유 |
|------|------|
| `케빈샘_완전동작_프로토타입_v3.html` | **기본 원본.** 모든 화면 작업의 출발점 |
| `kevinsaem_v31_dev/templates/` | **참고 코드.** 기존 Jinja2 템플릿 구조, base.html, partials 패턴 |
| `kevinsaem_v31_dev/static/` | **참고 코드.** CSS 변수, JS 유틸리티 함수, booking.js 상태관리 |
| `agents/agent_backend.md` | API 엔드포인트 확인 — HTMX 요청 경로 |
| `agents/agent_db.md` | 데이터 필드명 확인 — 템플릿 변수명 |

---

## 프로토타입 → 템플릿 매핑

프로토타입의 `<template x-if="p==='...'">` 블록을 각각 독립 Jinja2 파일로 분리한다.

| 프로토타입 섹션 | 템플릿 파일 | 경로 |
|----------------|------------|------|
| 1. 로그인 (`p==='login'`) | `login.html` | `templates/booking/login.html` |
| 2. 홈 (`p==='home'`) | `home.html` | `templates/booking/home.html` |
| 3. 예약 (`p==='booking'`) | `reserve.html` | `templates/booking/reserve.html` |
| 4. 반복예약 (`p==='repeat'`) | `repeat.html` | `templates/booking/repeat.html` |
| 5. 예약확인 (`p==='confirm'`) | `confirm.html` | `templates/booking/confirm.html` |
| 6. 예약완료 (`p==='complete'`) | `complete.html` | `templates/booking/complete.html` |
| 7. 내 예약 (`p==='mybk'`) | `my_bookings.html` | `templates/booking/my_bookings.html` |
| 8. 학습 대시보드 (`p==='dash'`) | `dashboard.html` | `templates/booking/dashboard.html` |
| 9. 메시지 (`p==='msg'`) | `messages.html` | `templates/booking/messages.html` |
| 10. 채팅방 (`p==='chat'`) | `chat.html` | `templates/booking/chat.html` |
| 11. 수강/결제 (`p==='pay'`) | `payment.html` | `templates/booking/payment.html` |
| 12. 공지사항 (`p==='notice'`) | `notices.html` | `templates/booking/notices.html` |
| 12-1. 공지 상세 (`p==='noticeDetail'`) | `notice_detail.html` | `templates/booking/notice_detail.html` |
| 13. MY (`p==='my'`) | `mypage.html` | `templates/booking/mypage.html` |

### HTMX 파셜 템플릿

| 파셜 | 설명 |
|------|------|
| `partials/time_slots.html` | 선택 날짜의 시간 슬롯 목록 |
| `partials/teachers.html` | 선택 시간의 강사 목록 |
| `partials/repeat_weeks.html` | 반복 예약 주차 목록 |
| `partials/booking_list.html` | 내 예약 목록 |
| `partials/chat_messages.html` | 채팅 메시지 목록 |
| `partials/notice_list.html` | 공지사항 목록 (탭 필터) |

---

## 디자인 시스템 (프로토타입에서 추출)

### 색상
| 이름 | 코드 | 용도 |
|------|------|------|
| `nv-600` | `#43A047` | 메인 브랜드 색 (버튼, 헤더) |
| `nv-50` | `#E8F5E9` | 연한 배경 |
| `g-100` | `#F5F5F5` | 페이지 배경 |
| `g-800` | `#424242` | 본문 텍스트 |
| `g-400` | `#BDBDBD` | 보조 텍스트 |

### 레이아웃
- 최대 너비: `430px` (모바일 최적화)
- 하단 탭 네비게이션: 홈, 예약, 학습, 메시지, MY
- 카드 스타일: `border-radius: 16px`, 미세 그림자
- 폰트: Noto Sans KR

### 인터랙션
- 페이드 업 애니메이션 (`.fade`)
- 터치 피드백 (`active:scale-[.97]`, `active:bg-g-50`)
- 프로그레스 바 (예약 단계별)
- 토스트 메시지 (하단)

---

## HTMX 전환 가이드

프로토타입에서 Alpine.js `@click="go('...')"` 으로 처리되던 화면 전환을:
- **전체 페이지 이동** → `<a href="/booking/...">`
- **부분 업데이트** → `hx-get="/booking/reserve/slots?date=..." hx-target="#slot-list"`
- **폼 제출** → `hx-post="/booking/reserve/submit" hx-target="body"`

Alpine.js는 **클라이언트 로직에만** 사용:
- 캘린더 날짜 선택 UI
- 토스트 메시지 표시
- 드롭다운/모달 토글
- 폼 유효성 검사

---

## 산출물

| 파일 | 설명 | 상태 |
|------|------|------|
| `templates/base.html` | 공통 레이아웃 | ⬜ 미착수 |
| `templates/components/tab_nav.html` | 하단 탭 네비게이션 | ⬜ 미착수 |
| `templates/components/toast.html` | 토스트 메시지 | ⬜ 미착수 |
| `templates/booking/login.html` | 로그인 | ⬜ 미착수 |
| `templates/booking/home.html` | 홈 | ⬜ 미착수 |
| `templates/booking/reserve.html` | 예약 (캘린더) | ⬜ 미착수 |
| `templates/booking/repeat.html` | 반복 예약 | ⬜ 미착수 |
| `templates/booking/confirm.html` | 예약 확인 | ⬜ 미착수 |
| `templates/booking/complete.html` | 예약 완료 | ⬜ 미착수 |
| `templates/booking/my_bookings.html` | 내 예약 | ⬜ 미착수 |
| `templates/booking/dashboard.html` | 학습 대시보드 | ⬜ 미착수 |
| `templates/booking/messages.html` | 메시지 목록 | ⬜ 미착수 |
| `templates/booking/chat.html` | 채팅방 | ⬜ 미착수 |
| `templates/booking/payment.html` | 수강/결제 | ⬜ 미착수 |
| `templates/booking/notices.html` | 공지사항 | ⬜ 미착수 |
| `templates/booking/notice_detail.html` | 공지 상세 | ⬜ 미착수 |
| `templates/booking/mypage.html` | MY 페이지 | ⬜ 미착수 |
| `templates/partials/` | HTMX 파셜 템플릿들 | ⬜ 미착수 |
| `static/css/custom.css` | 커스텀 스타일 | ⬜ 미착수 |
| `static/js/app.js` | 공통 Alpine.js 로직 | ⬜ 미착수 |

---

## 현재 상태

`✅ 완료` — 2026-03-23 Phase 3 완료
- base.html + 14개 페이지 템플릿 + 6개 파셜 + 3개 정적 파일 생성
- 프로토타입 HTML 디자인 그대로 반영 (색상, 레이아웃, 애니메이션)
- 전체 페이지 렌더링 테스트 통과

---

## 인바운드 알림

> 다른 에이전트가 이 에이전트에게 전달할 내용을 여기에 남긴다.

(아직 없음)
