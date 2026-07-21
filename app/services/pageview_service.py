# app/services/pageview_service.py
# 랜딩페이지 방문 기록 서비스
# - ensure_pageview_table(): 서버 시작 시 테이블 자동 생성 (SQLite/MS-SQL 모두)
# - record_pageview(): 방문 1건 기록 (미들웨어에서 호출)

from app.database import execute_query, DB_MODE

# 통계를 수집하는 랜딩페이지 (경로 → 관리자 화면 표시 이름)
LANDING_PAGES = {
    "/": "홈 (메인)",
    "/youth": "유소년 코딩",
    "/adult": "성인 코딩",
    "/autobiography": "자서전 쓰기",
    "/corporate": "기업 교육",
    "/corporate-survey": "기업 설문",
    "/campus": "캠퍼스 안내",
    "/tuition/youth": "유소년 수강료",
    "/tuition/corporate": "기업 수강료",
    "/privacy": "개인정보처리방침",
    "/refund": "환불 규정",
}

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


def ensure_pageview_table() -> None:
    """ek_PageView 테이블이 없으면 생성 (배포 시 수동 마이그레이션 불필요)"""
    if DB_MODE == "development":
        execute_query("""
            CREATE TABLE IF NOT EXISTS ek_PageView (
                pv_id INTEGER PRIMARY KEY AUTOINCREMENT,
                pv_path TEXT NOT NULL,
                pv_referrer TEXT DEFAULT '',
                pv_user_agent TEXT DEFAULT '',
                pv_ip TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """, fetch="none")
        execute_query(
            "CREATE INDEX IF NOT EXISTS IX_PageView_path_date ON ek_PageView(pv_path, created_at)",
            fetch="none"
        )
    else:
        execute_query("""
            IF OBJECT_ID('ek_PageView', 'U') IS NULL
            BEGIN
                CREATE TABLE ek_PageView (
                    pv_id INT IDENTITY(1,1) PRIMARY KEY,
                    pv_path VARCHAR(100) NOT NULL,
                    pv_referrer NVARCHAR(500) DEFAULT '',
                    pv_user_agent NVARCHAR(500) DEFAULT '',
                    pv_ip VARCHAR(45) DEFAULT '',
                    created_at DATETIME2 DEFAULT GETDATE()
                );
                CREATE INDEX IX_PageView_path_date ON ek_PageView(pv_path, created_at);
            END
        """, fetch="none")
    print("✅ ek_PageView 테이블 준비 완료 (랜딩페이지 접속통계)")


def record_pageview(path: str, referrer: str, user_agent: str, ip: str) -> None:
    """방문 1건 기록 (실패해도 페이지 응답에는 영향 없음)"""
    execute_query(
        """INSERT INTO ek_PageView (pv_path, pv_referrer, pv_user_agent, pv_ip, created_at)
           VALUES (?, ?, ?, ?, datetime('now','localtime'))""",
        (path[:100], (referrer or "")[:500], (user_agent or "")[:500], (ip or "")[:45]),
        fetch="none",
    )
