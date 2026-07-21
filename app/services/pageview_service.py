# app/services/pageview_service.py
# 랜딩페이지 방문 기록 서비스 (마케팅 반응 측정용 — 가능한 많은 정보 수집)
# - ensure_pageview_table(): 서버 시작 시 테이블 자동 생성 (SQLite/MS-SQL 모두)
# - record_pageview(): 방문 1건 기록 (미들웨어에서 호출)
# 통계 화면은 관리자 시스템 프로젝트에서 조회 전용으로 구현한다.
# 수집 항목 명세: 작업지시서_접속통계_관리자메뉴.md

import re
from urllib.parse import urlparse, parse_qs
from app.database import execute_query, DB_MODE

# 통계를 수집하는 랜딩페이지 (경로 → 관리자 화면 표시 이름)
LANDING_PAGES = {
    "/": "홈 (메인)",
    "/youth": "청소년 코딩",
    "/adult": "성인 1:1 AI활용",
    "/corporate": "기업 AI교육",
    "/autobiography": "AI자서전 출판",
    "/campus": "캠퍼스",
    "/corporate-survey": "기업 설문",
    "/tuition/youth": "청소년 수강료",
    "/tuition/corporate": "기업 수강료",
    "/privacy": "개인정보처리방침",
    "/refund": "환불 규정",
}

# 외부 사이트로 넘겨주는 중계 경로 (302 리다이렉트 시점에 클릭 1건 기록)
OUTBOUND_PAGES = {
    "/plaza": "작품소개 (game.kevinsaem.com)",
}

TRACKED_PAGES = {**LANDING_PAGES, **OUTBOUND_PAGES}

# 봇/크롤러 User-Agent 키워드 (통계에서 제외)
_BOT_KEYWORDS = (
    "bot", "crawler", "spider", "slurp", "curl", "wget",
    "python-requests", "httpx", "headless", "lighthouse",
    "yeti", "daumoa", "facebookexternalhit", "kakaotalk-scrap",
    "whatsapp", "telegrambot", "monitoring", "uptime",
)


def is_bot(user_agent: str) -> bool:
    """봇/크롤러 여부 판별 (User-Agent 기반)"""
    if not user_agent:
        return True
    ua = user_agent.lower()
    return any(k in ua for k in _BOT_KEYWORDS)


def _ref_host(referrer: str) -> str:
    """유입 출처 URL에서 도메인만 추출 (www. 제거) — 예: https://www.google.com/search → google.com"""
    if not referrer:
        return ""
    try:
        host = urlparse(referrer).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _device_type(user_agent: str) -> str:
    """기기 구분: mobile / tablet / pc"""
    ua = user_agent or ""
    if re.search(r"iPad|Tablet", ua, re.IGNORECASE) or ("Android" in ua and "Mobile" not in ua):
        return "tablet"
    if re.search(r"Mobile|Android|iPhone|iPod|BlackBerry|IEMobile", ua, re.IGNORECASE):
        return "mobile"
    return "pc"


def _parse_utm(query_string: str) -> tuple:
    """쿼리스트링에서 UTM 마케팅 파라미터 추출 → (source, medium, campaign)"""
    if not query_string:
        return "", "", ""
    try:
        q = parse_qs(query_string)
        get = lambda k: (q.get(k) or [""])[0]
        return get("utm_source"), get("utm_medium"), get("utm_campaign")
    except Exception:
        return "", "", ""


# 스키마 동기화 대상 컬럼: 컬럼명 → (SQLite 타입, MS-SQL 타입)
# 컬럼을 새로 추가하면 여기에도 등록할 것 — 기존 테이블에 자동으로 ALTER 된다.
_SYNC_COLUMNS = {
    "pv_query": ("TEXT DEFAULT ''", "NVARCHAR(500) DEFAULT ''"),
    "pv_ref_host": ("TEXT DEFAULT ''", "VARCHAR(100) DEFAULT ''"),
    "pv_utm_source": ("TEXT DEFAULT ''", "NVARCHAR(100) DEFAULT ''"),
    "pv_utm_medium": ("TEXT DEFAULT ''", "NVARCHAR(100) DEFAULT ''"),
    "pv_utm_campaign": ("TEXT DEFAULT ''", "NVARCHAR(200) DEFAULT ''"),
    "pv_device": ("TEXT DEFAULT ''", "VARCHAR(10) DEFAULT ''"),
}


def _sync_missing_columns() -> None:
    """구버전 스키마로 만들어진 테이블에 빠진 컬럼을 자동 추가 (재발 방지)"""
    if DB_MODE == "development":
        rows = execute_query("SELECT name FROM pragma_table_info('ek_PageView')")
        existing = {r["name"] for r in rows}
    else:
        rows = execute_query(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ek_PageView'"
        )
        existing = {r["COLUMN_NAME"] for r in rows}
    if not existing:
        return
    for col, (sqlite_type, mssql_type) in _SYNC_COLUMNS.items():
        if col not in existing:
            if DB_MODE == "development":
                execute_query(f"ALTER TABLE ek_PageView ADD COLUMN {col} {sqlite_type}", fetch="none")
            else:
                execute_query(f"ALTER TABLE ek_PageView ADD {col} {mssql_type}", fetch="none")
            print(f"🔧 ek_PageView 컬럼 추가: {col}")


def ensure_pageview_table() -> None:
    """ek_PageView 테이블이 없으면 생성, 있으면 빠진 컬럼 자동 추가 (배포 시 수동 마이그레이션 불필요)"""
    if DB_MODE == "development":
        execute_query("""
            CREATE TABLE IF NOT EXISTS ek_PageView (
                pv_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pv_path TEXT NOT NULL,
                pv_query TEXT DEFAULT '',
                pv_referrer TEXT DEFAULT '',
                pv_ref_host TEXT DEFAULT '',
                pv_utm_source TEXT DEFAULT '',
                pv_utm_medium TEXT DEFAULT '',
                pv_utm_campaign TEXT DEFAULT '',
                pv_device TEXT DEFAULT '',
                pv_user_agent TEXT DEFAULT '',
                pv_ip TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """, fetch="none")
        execute_query(
            "CREATE INDEX IF NOT EXISTS IX_PageView_path_date ON ek_PageView(pv_path, created_at)",
            fetch="none"
        )
        execute_query(
            "CREATE INDEX IF NOT EXISTS IX_PageView_date ON ek_PageView(created_at)",
            fetch="none"
        )
    else:
        execute_query("""
            IF OBJECT_ID('ek_PageView', 'U') IS NULL
            BEGIN
                CREATE TABLE ek_PageView (
                    pv_id INT IDENTITY(1,1) PRIMARY KEY,
                    pv_path VARCHAR(100) NOT NULL,
                    pv_query NVARCHAR(500) DEFAULT '',
                    pv_referrer NVARCHAR(500) DEFAULT '',
                    pv_ref_host VARCHAR(100) DEFAULT '',
                    pv_utm_source NVARCHAR(100) DEFAULT '',
                    pv_utm_medium NVARCHAR(100) DEFAULT '',
                    pv_utm_campaign NVARCHAR(200) DEFAULT '',
                    pv_device VARCHAR(10) DEFAULT '',
                    pv_user_agent NVARCHAR(500) DEFAULT '',
                    pv_ip VARCHAR(45) DEFAULT '',
                    created_at DATETIME2 DEFAULT GETDATE()
                );
                CREATE INDEX IX_PageView_path_date ON ek_PageView(pv_path, created_at);
                CREATE INDEX IX_PageView_date ON ek_PageView(created_at);
            END
        """, fetch="none")
    _sync_missing_columns()
    print("✅ ek_PageView 테이블 준비 완료 (랜딩페이지 접속통계)")


def record_pageview(path: str, query_string: str, referrer: str, user_agent: str, ip: str) -> None:
    """방문 1건 기록 (실패해도 페이지 응답에는 영향 없음)"""
    utm_source, utm_medium, utm_campaign = _parse_utm(query_string)
    execute_query(
        """INSERT INTO ek_PageView
           (pv_path, pv_query, pv_referrer, pv_ref_host,
            pv_utm_source, pv_utm_medium, pv_utm_campaign,
            pv_device, pv_user_agent, pv_ip, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))""",
        (
            path[:100],
            (query_string or "")[:500],
            (referrer or "")[:500],
            _ref_host(referrer)[:100],
            (utm_source or "")[:100],
            (utm_medium or "")[:100],
            (utm_campaign or "")[:200],
            _device_type(user_agent),
            (user_agent or "")[:500],
            (ip or "")[:45],
        ),
        fetch="none",
    )
