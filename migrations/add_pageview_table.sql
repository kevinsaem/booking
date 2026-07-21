-- 랜딩페이지 접속통계 테이블 (참고용)
-- 실행 대상: MS-SQL (프로덕션)
-- ※ 수동 실행 불필요: 서버 시작 시 app/services/pageview_service.py의
--   ensure_pageview_table()이 자동으로 생성한다. (SQLite도 동일)

IF OBJECT_ID('ek_PageView', 'U') IS NULL
BEGIN
    CREATE TABLE ek_PageView (
        pv_id INT IDENTITY(1,1) PRIMARY KEY,
        pv_path VARCHAR(100) NOT NULL,            -- 방문 경로 (예: /youth)
        pv_query NVARCHAR(500) DEFAULT '',        -- 쿼리스트링 원본 (utm 포함 전체)
        pv_referrer NVARCHAR(500) DEFAULT '',     -- 유입 출처 URL 원본 (Referer 헤더)
        pv_ref_host VARCHAR(100) DEFAULT '',      -- 유입 출처 도메인 (www. 제거, 예: google.com)
        pv_utm_source NVARCHAR(100) DEFAULT '',   -- 마케팅: utm_source
        pv_utm_medium NVARCHAR(100) DEFAULT '',   -- 마케팅: utm_medium
        pv_utm_campaign NVARCHAR(200) DEFAULT '', -- 마케팅: utm_campaign
        pv_device VARCHAR(10) DEFAULT '',         -- 기기: mobile / tablet / pc
        pv_user_agent NVARCHAR(500) DEFAULT '',   -- 브라우저 정보 (봇은 기록 안 함)
        pv_ip VARCHAR(45) DEFAULT '',             -- 방문자 IP
        created_at DATETIME2 DEFAULT GETDATE()    -- 방문 시각 (KST)
    );
    CREATE INDEX IX_PageView_path_date ON ek_PageView(pv_path, created_at);
    CREATE INDEX IX_PageView_date ON ek_PageView(created_at);
END
