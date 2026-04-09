# 케빈샘 AI코딩 예약 시스템 — 개발 시작 가이드

> Mac + VS Code + Python 3.10+ + Claude Code 환경 기준
> 이 가이드를 순서대로 따라하면 30분 안에 개발을 시작할 수 있습니다

---

## STEP 1: Claude Code 설치 (5분)

### 1-1. Mac 터미널 열기
Spotlight(⌘ + Space) → "터미널" 검색 → 실행

### 1-2. Claude Code 설치
```bash
# 네이티브 설치 (추천, Node.js 필요 없음)
curl -fsSL https://claude.ai/install.sh | bash
```

설치 후 새 터미널 탭을 열어주세요.

### 1-3. 설치 확인
```bash
claude --version
```
버전 번호가 나오면 성공입니다.

### 1-4. Claude Code 로그인
```bash
claude
```
브라우저가 열리면 Anthropic 계정으로 로그인합니다.
(Claude Pro, Max, Teams, Enterprise 중 하나 필요)

---

## STEP 2: 프로젝트 세팅 (10분)

### 2-1. 프로젝트 폴더 생성
```bash
# 홈 디렉토리에 프로젝트 폴더 생성
mkdir -p ~/projects/kevinsaem-booking
cd ~/projects/kevinsaem-booking
```

### 2-2. ZIP 파일 압축 해제
다운로드한 `kevinsaem_v31_dev.zip`을 프로젝트 폴더에 압축 해제합니다.
```bash
# ZIP 파일을 프로젝트 폴더로 이동 후 해제
cp ~/Downloads/kevinsaem_v31_dev.zip .
unzip kevinsaem_v31_dev.zip
rm kevinsaem_v31_dev.zip
```

### 2-3. 폴더 구조 확인
```bash
ls -la
```
이런 구조가 보여야 합니다:
```
kevinsaem-booking/
├── main.py              ← FastAPI 앱 진입점
├── requirements.txt     ← Python 의존성
├── .env                 ← 환경변수 (DB_MODE=development)
├── Dockerfile
├── app/
│   ├── config.py
│   ├── database.py      ← 듀얼 모드 (SQLite/MS-SQL)
│   ├── seed.py          ← Mock 데이터 생성
│   ├── routers/
│   ├── services/
│   └── models/
├── templates/           ← Jinja2 HTML 템플릿 (13개 화면)
│   ├── base.html
│   ├── booking/
│   └── partials/
├── static/              ← CSS, JS
│   ├── css/
│   └── js/
└── scripts/
    └── reset_db.py      ← DB 리셋 도구
```

### 2-4. Python 가상환경 생성
```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 프롬프트가 (venv)로 바뀌면 성공
```

### 2-5. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2-6. 개발 DB 생성 (SQLite + Mock 데이터)
```bash
python scripts/reset_db.py
```

이런 출력이 나와야 합니다:
```
→ 수강생 5명, 강사 3명, 패키지 3개, 슬롯 약 165개 생성
✅ 개발 DB 재생성 완료

📂 DB 파일: /Users/you/projects/kevinsaem-booking/dev.db
📏 크기: 56.0 KB

테이블                         레코드 수
------------------------------------------
ek_EduCenter                        2
ek_Member                           8
ek_Package                          3
ek_Settlement                       5
ek_Sch_Detail_Room                165
ek_Sch_Detail_Room_mem             13
dev_messages                        5
dev_notices                         4
```

### 2-7. 서버 실행
```bash
uvicorn main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000/booking/` 열면 로그인 화면이 보입니다.

> 아직은 Jinja2 템플릿이 서버에서 렌더링되는 상태가 아니므로
> 프로토타입 HTML 파일을 브라우저에서 직접 열어서 확인하세요.

---

## STEP 3: VS Code로 열기 (2분)

### 3-1. VS Code에서 프로젝트 열기
```bash
code ~/projects/kevinsaem-booking
```

### 3-2. 추천 VS Code 확장 프로그램
- **Python** (Microsoft) — Python 자동완성, 린팅
- **Jinja** (wholroyd) — Jinja2 템플릿 하이라이팅
- **Tailwind CSS IntelliSense** — Tailwind 자동완성
- **Claude Code** — VS Code 내 Claude Code 연동 (선택)

### 3-3. VS Code 터미널 열기
`Ctrl + ~` 로 터미널 열고, 가상환경 활성화:
```bash
source venv/bin/activate
```

---

## STEP 4: Claude Code로 바이브 코딩 시작 (계속)

### 4-1. Claude Code 실행
VS Code 터미널 또는 별도 터미널에서:
```bash
cd ~/projects/kevinsaem-booking
claude
```

### 4-2. 첫 번째 명령 — 프로젝트 이해시키기
Claude Code에 이렇게 말하세요:
```
이 프로젝트를 분석해줘. 
케빈샘 AI코딩 성인 1:1 예약 시스템이야.
기술 스택은 FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind CSS.
DB는 개발 모드에서 SQLite를 쓰고, 프로덕션에서는 MS-SQL로 전환해.
main.py부터 시작해서 전체 구조를 파악하고 요약해줘.
```

### 4-3. CLAUDE.md 생성 (매우 중요!)
프로젝트 루트에 `CLAUDE.md` 파일을 만들어두면 Claude Code가 프로젝트를 더 잘 이해합니다:

```bash
# Claude Code에게 말하세요:
"프로젝트 루트에 CLAUDE.md 파일을 만들어줘.
이 프로젝트의 기술 스택, 폴더 구조, 코딩 규칙, 
DB 연결 방식, 테스트 데이터 정보를 포함해줘."
```

### 4-4. 개발 시작 — 추천 순서

Claude Code에게 이렇게 순서대로 요청하세요:

**Phase 1: 서버 부팅 가능하게 만들기**
```
main.py를 수정해서 uvicorn으로 서버가 정상 실행되게 해줘.
/booking/ 접속하면 login.html이 렌더링되어야 해.
Jinja2 템플릿 경로와 정적 파일 경로를 확인하고 수정해줘.
```

**Phase 2: 로그인 동작시키기**
```
로그인 기능을 구현해줘.
POST /booking/login에서 이름+인증번호로 SQLite DB를 조회하고,
성공하면 JWT 쿠키를 설정하고 홈으로 리다이렉트해.
테스트 계정: 김수강/1234
```

**Phase 3: 홈 화면 데이터 연동**
```
/booking/ 홈 화면에서 실제 DB 데이터가 표시되게 해줘.
잔여 수업 횟수, 다가오는 수업, 공지사항을 SQLite에서 조회해서
home.html 템플릿에 전달해줘.
```

**Phase 4: 예약 흐름 구현**
```
캘린더에서 날짜를 선택하면 HTMX로 시간 슬롯을 로드하고,
시간을 선택하면 강사 목록을 로드하는 흐름을 구현해줘.
partials/ 폴더의 HTML 조각들을 사용해.
```

---

## STEP 5: 자주 쓰는 명령어 모음

### 서버
```bash
# 서버 시작 (자동 새로고침)
uvicorn main:app --reload --port 8000

# 서버 중단
Ctrl + C
```

### 데이터베이스
```bash
# DB 리셋 (데이터 초기화)
python scripts/reset_db.py

# DB 상태 확인
python scripts/reset_db.py --check

# DB 상세 통계
python scripts/reset_db.py --stats
```

### Claude Code
```bash
# Claude Code 시작
claude

# 특정 파일 분석 요청
# (Claude Code 내에서)
"app/routers/booking_pages.py를 분석해줘"

# 버그 수정 요청
"서버 실행하면 ImportError가 나와. 로그 보여줄테니 수정해줘"

# 테스트 실행
"pytest tests/ 를 실행하고 실패하는 테스트를 수정해줘"
```

### Git (버전 관리)
```bash
# 첫 커밋
git init
git add .
git commit -m "초기 프로젝트 세팅"

# 기능 단위 커밋 (Claude Code에게 맡기기)
# Claude Code 내에서:
"지금까지 변경사항을 git commit 해줘. 커밋 메시지는 한국어로."
```

---

## 테스트 계정 정보

| 이름 | 인증번호 | ID | 패키지 | 잔여 |
|------|---------|-----|--------|------|
| 김수강 | 1234 | STU001 | 진로반 20회 | 7회 |
| 이학생 | 5678 | STU002 | 취미반 8회 | 8회 |
| 박공부 | 9012 | STU003 | 월정기 40회 | 40회 |
| 최열심 | 3456 | STU004 | 진로반 20회 | 20회 |
| 정성실 | 7890 | STU005 | 취미반 8회 | 8회 |

강사: 김코딩(TEA001), 박데이터(TEA002), 이웹개발(TEA003)

---

## 트러블슈팅

### "ModuleNotFoundError" 에러
```bash
# 가상환경이 활성화되어 있는지 확인
which python
# /Users/you/projects/kevinsaem-booking/venv/bin/python 이어야 함

# 안 되면 다시 활성화
source venv/bin/activate
pip install -r requirements.txt
```

### "Address already in use" 에러
```bash
# 이미 실행 중인 서버 종료
lsof -i :8000
kill -9 <PID>
```

### DB 데이터가 이상할 때
```bash
# DB 완전 리셋
python scripts/reset_db.py
```

### Claude Code가 프로젝트를 못 찾을 때
```bash
# 반드시 프로젝트 폴더에서 실행
cd ~/projects/kevinsaem-booking
claude
```

---

## 다음 단계

이 가이드로 개발 환경이 준비되면:
1. Claude Code로 Phase 1~4를 순서대로 진행
2. 각 화면이 동작하면 git commit
3. 전체 예약 흐름이 완성되면 Sprint 1 완료
4. 이후 학습 대시보드, 메시지, 결제 화면 순서로 개발

궁금한 점은 이 채팅에서 언제든 물어보세요!
