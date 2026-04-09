-- 전자서명 테이블 마이그레이션
-- 실행 대상: MS-SQL (프로덕션)
-- SQLite는 seed.py에서 자동 생성

-- 계약서 템플릿
CREATE TABLE agreement_templates (
    id INT IDENTITY(1,1) PRIMARY KEY,
    version VARCHAR(10) NOT NULL,
    title NVARCHAR(200) NOT NULL,
    content NVARCHAR(MAX) NOT NULL,
    course_type NVARCHAR(100) NOT NULL,
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE()
);

-- 전자서명 기록
CREATE TABLE agreement_signatures (
    id INT IDENTITY(1,1) PRIMARY KEY,
    mem_MbrId VARCHAR(100) NOT NULL,
    template_id INT NOT NULL,
    signature_image NVARCHAR(MAX) NOT NULL,
    agreed_at DATETIME2 NOT NULL DEFAULT GETDATE(),
    ip_address VARCHAR(45),
    user_agent NVARCHAR(500),
    device_info NVARCHAR(200),
    document_hash VARCHAR(64),
    is_valid BIT DEFAULT 1,
    CONSTRAINT FK_sig_member FOREIGN KEY (mem_MbrId) REFERENCES ek_Member(mem_MbrId),
    CONSTRAINT FK_sig_template FOREIGN KEY (template_id) REFERENCES agreement_templates(id)
);

CREATE INDEX IX_sig_member ON agreement_signatures(mem_MbrId);
CREATE INDEX IX_sig_template ON agreement_signatures(template_id);
