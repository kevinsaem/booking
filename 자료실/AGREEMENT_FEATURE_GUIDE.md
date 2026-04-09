# 수강원칙 전자서명 기능 구현 가이드

> **목적**: 케빈샘AI코딩학원 booking 프로젝트에 "교육 서비스 이용 계약서" 전자서명 기능을 추가한다.
> **실행 환경**: Claude Code 터미널
> **기술 스택**: FastAPI + HTMX + Tailwind CSS + Jinja2 + MS-SQL (pymssql 또는 pyodbc)
> **인증 방식**: 전화번호 SMS 인증 (기존 시스템 활용)

---

## 1. 개요

### 1.1 기능 요약

수강생이 모바일 웹에서 수강 등록 시 "교육 서비스 이용 계약서"를 확인하고 전자서명하는 기능.

### 1.2 사용자 플로우

```
수강생 SMS 인증 로그인
    → 수강 등록 진행
    → 계약서 전문 표시 (스크롤 필수)
    → 동의 체크박스 (전체 내용 확인 완료)
    → 서명 패드에 자필 서명
    → 제출 → DB 저장 + 서명 이미지 저장
    → 완료 화면 (서명 완료 일시 표시)
```

### 1.3 핵심 원칙

- 계약서 전문을 끝까지 스크롤해야 동의 체크박스 활성화
- 자필 서명(Canvas)은 필수
- 서명 데이터는 base64 PNG로 DB 저장
- 서명 시점의 IP, User-Agent, 타임스탬프 기록
- 한 번 서명한 계약서는 수정 불가 (읽기 전용 조회만 가능)

---

## 2. DB 스키마

### 2.1 계약서 템플릿 테이블

```sql
CREATE TABLE agreement_templates (
    id INT IDENTITY(1,1) PRIMARY KEY,
    version VARCHAR(10) NOT NULL,           -- 'v1.0', 'v1.1' 등
    title NVARCHAR(200) NOT NULL,           -- '교육 서비스 이용 계약서'
    content NVARCHAR(MAX) NOT NULL,         -- 계약서 전문 (Markdown 또는 HTML)
    course_type NVARCHAR(100) NOT NULL,     -- '1:1 성인 AI 활용 과정'
    is_active BIT DEFAULT 1,               -- 현재 사용 중인 버전
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE()
);
```

### 2.2 전자서명 기록 테이블

```sql
CREATE TABLE agreement_signatures (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id INT NOT NULL,                -- students 테이블 FK
    template_id INT NOT NULL,               -- agreement_templates FK
    signature_image NVARCHAR(MAX) NOT NULL,  -- base64 PNG 서명 이미지
    agreed_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    ip_address VARCHAR(45),                 -- IPv4/IPv6
    user_agent NVARCHAR(500),               -- 브라우저 정보
    device_info NVARCHAR(200),              -- 모바일/데스크톱 구분
    document_hash VARCHAR(64),              -- 서명 시점 계약서 SHA-256 해시
    is_valid BIT DEFAULT 1,                 -- 유효 여부
    CONSTRAINT FK_sig_student FOREIGN KEY (student_id) REFERENCES students(id),
    CONSTRAINT FK_sig_template FOREIGN KEY (template_id) REFERENCES agreement_templates(id)
);

-- 인덱스
CREATE INDEX IX_sig_student ON agreement_signatures(student_id);
CREATE INDEX IX_sig_template ON agreement_signatures(template_id);
```

### 2.3 마이그레이션 실행

```bash
# 프로젝트 루트에서 SQL 파일 생성 후 실행
# 또는 Alembic을 사용 중이라면 마이그레이션 스크립트로 생성
```

---

## 3. 백엔드 구현

### 3.1 파일 구조 (추가/수정 대상)

```
booking/
├── app/
│   ├── models/
│   │   └── agreement.py          # 신규: 계약서 모델
│   ├── routes/
│   │   └── agreement.py          # 신규: 계약서 라우터
│   ├── services/
│   │   └── agreement_service.py  # 신규: 계약서 비즈니스 로직
│   ├── templates/
│   │   └── agreement/
│   │       ├── view.html         # 신규: 계약서 열람 + 서명 페이지
│   │       ├── signed.html       # 신규: 서명 완료 페이지
│   │       └── history.html      # 신규: 서명 이력 조회 페이지
│   └── static/
│       └── js/
│           └── signature-pad.js  # 신규: 서명 패드 JS
├── agreement_content.md          # 신규: 계약서 원문 (이 파일에서 DB에 시딩)
└── migrations/
    └── add_agreement_tables.sql  # 신규: DB 마이그레이션
```

### 3.2 모델 (app/models/agreement.py)

```python
"""
교육 서비스 이용 계약서 - 전자서명 모델
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AgreementTemplate:
    id: Optional[int] = None
    version: str = ""
    title: str = ""
    content: str = ""
    course_type: str = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class AgreementSignature:
    id: Optional[int] = None
    student_id: int = 0
    template_id: int = 0
    signature_image: str = ""       # base64 PNG
    agreed_at: Optional[datetime] = None
    ip_address: str = ""
    user_agent: str = ""
    device_info: str = ""
    document_hash: str = ""
    is_valid: bool = True
```

### 3.3 서비스 (app/services/agreement_service.py)

```python
"""
계약서 전자서명 비즈니스 로직
"""
import hashlib
from datetime import datetime
from typing import Optional

# DB 커넥션은 프로젝트의 기존 패턴을 따를 것
# 예: from app.database import get_db_connection


async def get_active_template(course_type: str = "1:1 성인 AI 활용 과정") -> Optional[dict]:
    """현재 활성화된 계약서 템플릿 조회"""
    query = """
        SELECT id, version, title, content, course_type, created_at
        FROM agreement_templates
        WHERE is_active = 1 AND course_type = %s
        ORDER BY created_at DESC
    """
    # 기존 DB 커넥션 패턴 사용하여 실행
    # row = await db.fetch_one(query, (course_type,))
    # return row
    pass


async def check_student_signed(student_id: int, template_id: int) -> bool:
    """해당 수강생이 이미 서명했는지 확인"""
    query = """
        SELECT COUNT(*) as cnt
        FROM agreement_signatures
        WHERE student_id = %s AND template_id = %s AND is_valid = 1
    """
    # result = await db.fetch_one(query, (student_id, template_id))
    # return result['cnt'] > 0
    pass


def compute_document_hash(content: str) -> str:
    """계약서 내용의 SHA-256 해시 생성 (무결성 검증용)"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


async def save_signature(
    student_id: int,
    template_id: int,
    signature_image: str,
    ip_address: str,
    user_agent: str,
    device_info: str,
    document_hash: str
) -> int:
    """전자서명 저장"""
    query = """
        INSERT INTO agreement_signatures
        (student_id, template_id, signature_image, agreed_at,
         ip_address, user_agent, device_info, document_hash, is_valid)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
    """
    params = (
        student_id, template_id, signature_image,
        datetime.now(), ip_address, user_agent,
        device_info, document_hash
    )
    # result = await db.execute(query, params)
    # return result.lastrowid
    pass


async def get_signature_history(student_id: int) -> list:
    """수강생의 서명 이력 조회"""
    query = """
        SELECT s.id, s.agreed_at, s.ip_address, s.device_info,
               t.version, t.title, t.course_type
        FROM agreement_signatures s
        JOIN agreement_templates t ON s.template_id = t.id
        WHERE s.student_id = %s AND s.is_valid = 1
        ORDER BY s.agreed_at DESC
    """
    # rows = await db.fetch_all(query, (student_id,))
    # return rows
    pass
```

### 3.4 라우터 (app/routes/agreement.py)

```python
"""
계약서 전자서명 라우터
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from app.services import agreement_service

router = APIRouter(prefix="/agreement", tags=["agreement"])


@router.get("/", response_class=HTMLResponse)
async def view_agreement(request: Request):
    """계약서 열람 + 서명 페이지"""
    # 1. 현재 로그인한 수강생 정보 가져오기 (기존 세션/인증 활용)
    student = request.state.student  # 프로젝트 인증 패턴에 맞게 수정

    # 2. 활성 계약서 템플릿 조회
    template = await agreement_service.get_active_template()
    if not template:
        raise HTTPException(status_code=404, detail="계약서를 찾을 수 없습니다.")

    # 3. 이미 서명했는지 확인
    already_signed = await agreement_service.check_student_signed(
        student.id, template['id']
    )

    if already_signed:
        # 이미 서명한 경우 → 서명 완료 페이지로
        return templates.TemplateResponse("agreement/signed.html", {
            "request": request,
            "student": student,
            "template": template,
            "already_signed": True
        })

    # 4. 서명 전 → 계약서 + 서명 패드 페이지
    document_hash = agreement_service.compute_document_hash(template['content'])

    return templates.TemplateResponse("agreement/view.html", {
        "request": request,
        "student": student,
        "template": template,
        "document_hash": document_hash
    })


@router.post("/sign")
async def sign_agreement(
    request: Request,
    template_id: int = Form(...),
    document_hash: str = Form(...),
    signature_data: str = Form(...)   # base64 PNG
):
    """전자서명 제출"""
    student = request.state.student

    # 중복 서명 방지
    already_signed = await agreement_service.check_student_signed(
        student.id, template_id
    )
    if already_signed:
        raise HTTPException(status_code=400, detail="이미 서명한 계약서입니다.")

    # 서명 데이터 검증
    if not signature_data or not signature_data.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=400, detail="유효하지 않은 서명 데이터입니다.")

    # 클라이언트 정보 수집
    ip_address = request.client.host
    user_agent = request.headers.get("user-agent", "")
    device_info = _detect_device(user_agent)

    # 저장
    sig_id = await agreement_service.save_signature(
        student_id=student.id,
        template_id=template_id,
        signature_image=signature_data,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info,
        document_hash=document_hash
    )

    # HTMX 응답: 서명 완료 화면으로 교체
    return templates.TemplateResponse("agreement/signed.html", {
        "request": request,
        "student": student,
        "signed_at": datetime.now(),
        "sig_id": sig_id
    })


@router.get("/history", response_class=HTMLResponse)
async def signature_history(request: Request):
    """서명 이력 조회"""
    student = request.state.student
    history = await agreement_service.get_signature_history(student.id)

    return templates.TemplateResponse("agreement/history.html", {
        "request": request,
        "student": student,
        "history": history
    })


def _detect_device(user_agent: str) -> str:
    """User-Agent로 디바이스 유형 판별"""
    ua_lower = user_agent.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return "모바일"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        return "태블릿"
    return "데스크톱"
```

### 3.5 메인 앱에 라우터 등록

```python
# app/main.py 또는 프로젝트의 라우터 등록 파일에 추가
from app.routes.agreement import router as agreement_router

app.include_router(agreement_router)
```

---

## 4. 프론트엔드 구현

### 4.1 계약서 열람 + 서명 페이지 (templates/agreement/view.html)

```html
{% extends "base.html" %}
{% block title %}교육 서비스 이용 계약서{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto px-4 py-6">

  <!-- 헤더 -->
  <div class="text-center mb-6">
    <h1 class="text-xl font-bold text-gray-900">교육 서비스 이용 계약서</h1>
    <p class="text-sm text-gray-500 mt-1">{{ template.version }} | {{ template.course_type }}</p>
  </div>

  <!-- 계약서 본문 (스크롤 영역) -->
  <div id="agreement-content"
       class="bg-white border border-gray-200 rounded-lg p-4 mb-4
              overflow-y-auto text-sm leading-relaxed text-gray-700"
       style="max-height: 50vh;"
       onscroll="checkScroll(this)">
    {{ template.content | safe }}
  </div>

  <!-- 스크롤 안내 -->
  <p id="scroll-notice" class="text-center text-xs text-orange-500 mb-4">
    ↓ 계약서 전문을 끝까지 읽어주세요
  </p>

  <!-- 동의 + 서명 영역 -->
  <form hx-post="/agreement/sign"
        hx-target="#agreement-wrapper"
        hx-swap="innerHTML"
        id="sign-form">

    <input type="hidden" name="template_id" value="{{ template.id }}">
    <input type="hidden" name="document_hash" value="{{ document_hash }}">
    <input type="hidden" name="signature_data" id="signature-data">

    <!-- 동의 체크박스 (스크롤 완료 전 비활성) -->
    <label class="flex items-start gap-3 mb-4 p-3 bg-gray-50 rounded-lg">
      <input type="checkbox" id="agree-check" disabled
             class="mt-1 w-5 h-5 rounded border-gray-300
                    text-blue-600 focus:ring-blue-500
                    disabled:opacity-40">
      <span class="text-sm text-gray-700">
        위 계약서의 모든 내용을 확인하였으며, 이에 동의합니다.
      </span>
    </label>

    <!-- 서명 패드 -->
    <div id="signature-section" class="mb-4 opacity-40 pointer-events-none">
      <p class="text-sm font-medium text-gray-700 mb-2">서명</p>
      <div class="relative border-2 border-dashed border-gray-300 rounded-lg bg-white">
        <canvas id="signature-canvas" class="w-full" style="height: 150px; touch-action: none;"></canvas>
        <button type="button" onclick="clearSignature()"
                class="absolute top-2 right-2 text-xs text-gray-400
                       hover:text-red-500 transition-colors">
          지우기
        </button>
      </div>
      <p class="text-xs text-gray-400 mt-1">위 영역에 서명해 주세요</p>
    </div>

    <!-- 수강생 정보 표시 -->
    <div class="bg-blue-50 rounded-lg p-3 mb-4 text-sm">
      <p class="text-gray-600">수강생: <strong class="text-gray-900">{{ student.name }}</strong></p>
      <p class="text-gray-600">연락처: <strong class="text-gray-900">{{ student.phone }}</strong></p>
    </div>

    <!-- 제출 버튼 -->
    <button type="submit" id="submit-btn" disabled
            class="w-full py-3 rounded-lg font-medium text-white
                   bg-blue-600 hover:bg-blue-700
                   disabled:bg-gray-300 disabled:cursor-not-allowed
                   transition-colors">
      동의 및 서명 제출
    </button>
  </form>
</div>

<script src="/static/js/signature-pad.js"></script>
<script>
  let hasScrolledToBottom = false;
  let hasSignature = false;
  let isAgreed = false;

  // 스크롤 완료 감지
  function checkScroll(el) {
    const threshold = 20; // px 여유
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - threshold) {
      hasScrolledToBottom = true;
      document.getElementById('scroll-notice').classList.add('hidden');
      document.getElementById('agree-check').disabled = false;
      document.getElementById('agree-check').classList.remove('opacity-40');
    }
  }

  // 동의 체크박스
  document.getElementById('agree-check').addEventListener('change', function() {
    isAgreed = this.checked;
    const sigSection = document.getElementById('signature-section');
    if (isAgreed) {
      sigSection.classList.remove('opacity-40', 'pointer-events-none');
    } else {
      sigSection.classList.add('opacity-40', 'pointer-events-none');
    }
    updateSubmitButton();
  });

  function updateSubmitButton() {
    const btn = document.getElementById('submit-btn');
    btn.disabled = !(isAgreed && hasSignature);
  }

  // 서명 제출 전 데이터 설정
  document.getElementById('sign-form').addEventListener('htmx:configRequest', function(e) {
    const dataUrl = getSignatureDataUrl();
    if (!dataUrl) {
      e.preventDefault();
      alert('서명을 해주세요.');
      return;
    }
    document.getElementById('signature-data').value = dataUrl;
  });
</script>
{% endblock %}
```

### 4.2 서명 패드 JS (static/js/signature-pad.js)

```javascript
/**
 * 캔버스 기반 서명 패드
 * 모바일 터치 + 데스크톱 마우스 모두 지원
 */
const canvas = document.getElementById('signature-canvas');
const ctx = canvas.getContext('2d');
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// 캔버스 크기를 실제 픽셀에 맞춤 (Retina 대응)
function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  ctx.strokeStyle = '#1a1a1a';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
}

resizeCanvas();
window.addEventListener('resize', resizeCanvas);

// 좌표 계산
function getPos(e) {
  const rect = canvas.getBoundingClientRect();
  const touch = e.touches ? e.touches[0] : e;
  return {
    x: touch.clientX - rect.left,
    y: touch.clientY - rect.top
  };
}

// 그리기 시작
function startDrawing(e) {
  e.preventDefault();
  isDrawing = true;
  const pos = getPos(e);
  lastX = pos.x;
  lastY = pos.y;
}

// 그리기
function draw(e) {
  e.preventDefault();
  if (!isDrawing) return;
  const pos = getPos(e);
  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(pos.x, pos.y);
  ctx.stroke();
  lastX = pos.x;
  lastY = pos.y;

  // 서명 상태 업데이트
  hasSignature = true;
  if (typeof updateSubmitButton === 'function') updateSubmitButton();
}

// 그리기 종료
function stopDrawing(e) {
  e.preventDefault();
  isDrawing = false;
}

// 마우스 이벤트
canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseleave', stopDrawing);

// 터치 이벤트 (모바일)
canvas.addEventListener('touchstart', startDrawing, { passive: false });
canvas.addEventListener('touchmove', draw, { passive: false });
canvas.addEventListener('touchend', stopDrawing);

// 서명 지우기
function clearSignature() {
  const dpr = window.devicePixelRatio || 1;
  ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
  hasSignature = false;
  if (typeof updateSubmitButton === 'function') updateSubmitButton();
}

// 서명 데이터 URL 반환
function getSignatureDataUrl() {
  if (!hasSignature) return null;
  return canvas.toDataURL('image/png');
}
```

### 4.3 서명 완료 페이지 (templates/agreement/signed.html)

```html
{% extends "base.html" %}
{% block title %}서명 완료{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto px-4 py-12 text-center">

  <!-- 완료 아이콘 -->
  <div class="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full
              flex items-center justify-center">
    <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor"
         viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M5 13l4 4L19 7"/>
    </svg>
  </div>

  <h1 class="text-xl font-bold text-gray-900 mb-2">서명이 완료되었습니다</h1>

  <p class="text-sm text-gray-500 mb-6">
    교육 서비스 이용 계약서에 전자서명이 완료되었습니다.
  </p>

  <div class="bg-gray-50 rounded-lg p-4 text-sm text-left mb-6">
    <div class="flex justify-between py-1">
      <span class="text-gray-500">수강생</span>
      <span class="font-medium">{{ student.name }}</span>
    </div>
    <div class="flex justify-between py-1">
      <span class="text-gray-500">과정</span>
      <span class="font-medium">1:1 성인 AI 활용 과정</span>
    </div>
    <div class="flex justify-between py-1">
      <span class="text-gray-500">서명 일시</span>
      <span class="font-medium">{{ signed_at.strftime('%Y-%m-%d %H:%M') }}</span>
    </div>
  </div>

  <a href="/"
     class="inline-block w-full py-3 rounded-lg font-medium text-white
            bg-blue-600 hover:bg-blue-700 transition-colors">
    홈으로 돌아가기
  </a>

</div>
{% endblock %}
```

### 4.4 서명 이력 조회 페이지 (templates/agreement/history.html)

```html
{% extends "base.html" %}
{% block title %}서명 이력{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto px-4 py-6">
  <h1 class="text-xl font-bold text-gray-900 mb-4">계약서 서명 이력</h1>

  {% if history %}
    {% for item in history %}
    <div class="bg-white border border-gray-200 rounded-lg p-4 mb-3">
      <div class="flex justify-between items-start">
        <div>
          <p class="font-medium text-gray-900">{{ item.title }}</p>
          <p class="text-xs text-gray-500">{{ item.course_type }} · {{ item.version }}</p>
        </div>
        <span class="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
          서명완료
        </span>
      </div>
      <div class="mt-2 text-xs text-gray-400">
        {{ item.agreed_at.strftime('%Y-%m-%d %H:%M') }} · {{ item.device_info }}
      </div>
    </div>
    {% endfor %}
  {% else %}
    <div class="text-center py-12 text-gray-400">
      <p>서명 이력이 없습니다.</p>
    </div>
  {% endif %}
</div>
{% endblock %}
```

---

## 5. 계약서 원문 (DB 시딩용)

아래 내용을 `agreement_content.md` 파일로 저장하고, 초기 데이터 시딩 스크립트에서 DB에 INSERT한다.

### 시딩 스크립트 예시

```python
"""
계약서 템플릿 초기 데이터 시딩
실행: python -m scripts.seed_agreement
"""
import hashlib
from pathlib import Path

# 프로젝트의 기존 DB 커넥션 활용
# from app.database import get_connection

def seed_agreement():
    content_path = Path(__file__).parent.parent / "agreement_content.md"
    content = content_path.read_text(encoding="utf-8")

    # Markdown → HTML 변환 (선택)
    # import markdown
    # html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])

    query = """
        INSERT INTO agreement_templates (version, title, content, course_type, is_active)
        VALUES (%s, %s, %s, %s, 1)
    """
    params = (
        'v1.0',
        '교육 서비스 이용 계약서',
        content,  # 또는 html_content
        '1:1 성인 AI 활용 과정'
    )
    # conn = get_connection()
    # cursor = conn.cursor()
    # cursor.execute(query, params)
    # conn.commit()
    print("✅ 계약서 템플릿 시딩 완료 (v1.0)")

if __name__ == "__main__":
    seed_agreement()
```

### 계약서 원문 (agreement_content.md)

아래 내용은 앞서 작성한 `교육서비스_이용계약서_성인과정.md`의 전문을 그대로 사용한다.
해당 파일을 프로젝트 루트에 `agreement_content.md`로 복사하여 사용할 것.

---

## 6. 수강 등록 플로우 연동

기존 수강 등록 프로세스에서 계약서 서명 단계를 삽입해야 한다.

### 6.1 수강 등록 라우터 수정

```python
# 기존 수강 등록 라우터에서 계약서 서명 여부 체크 추가
@router.get("/booking/register")
async def register(request: Request):
    student = request.state.student

    # 계약서 서명 여부 확인
    template = await agreement_service.get_active_template()
    if template:
        signed = await agreement_service.check_student_signed(
            student.id, template['id']
        )
        if not signed:
            # 서명 안 했으면 계약서 페이지로 리다이렉트
            return RedirectResponse(url="/agreement/", status_code=303)

    # 서명 완료 → 기존 등록 프로세스 진행
    ...
```

### 6.2 네비게이션 메뉴에 서명 이력 추가

```html
<!-- 수강생 메뉴에 추가 -->
<a href="/agreement/history" class="...">계약서 확인</a>
```

---

## 7. Claude Code 실행 순서

터미널에서 다음 순서로 실행하면 된다:

```
1. DB 마이그레이션 (agreement_templates, agreement_signatures 테이블 생성)
2. agreement_content.md 파일을 프로젝트 루트에 복사
3. app/models/agreement.py 생성
4. app/services/agreement_service.py 생성 (기존 DB 커넥션 패턴에 맞게 수정)
5. app/routes/agreement.py 생성 (기존 인증 미들웨어에 맞게 수정)
6. static/js/signature-pad.js 생성
7. templates/agreement/ 디렉토리에 view.html, signed.html, history.html 생성
8. main.py에 agreement 라우터 등록
9. 계약서 시딩 스크립트 실행
10. 수강 등록 라우터에 서명 체크 로직 추가
11. 테스트: 모바일 브라우저에서 /agreement/ 접속하여 전체 플로우 확인
```

---

## 8. 주의사항

- **DB 커넥션**: 이 가이드의 `# 기존 DB 커넥션 패턴 사용` 주석 부분을 프로젝트의 실제 DB 접속 방식(pymssql/pyodbc)에 맞게 수정할 것
- **인증 미들웨어**: `request.state.student` 부분을 프로젝트의 실제 인증 방식에 맞게 수정할 것
- **base.html**: 프로젝트의 실제 base 템플릿 파일명과 block 이름에 맞게 수정할 것
- **HTMX**: 프로젝트에 HTMX가 이미 로드되어 있다고 가정. 없으면 base.html에 `<script src="https://unpkg.com/htmx.org@2.0.4"></script>` 추가
- **Markdown 렌더링**: 계약서 내용을 HTML로 변환하여 DB에 저장하거나, 프론트에서 Markdown 렌더링 라이브러리 사용
- **서명 이미지 용량**: base64 PNG는 보통 10~50KB 정도이므로 MS-SQL의 NVARCHAR(MAX)로 충분
- **법적 효력**: 전자서명법에 따른 공인전자서명이 아닌 간이 전자서명이므로, 법적 분쟁 시 보조 증거 수준임을 인지할 것
