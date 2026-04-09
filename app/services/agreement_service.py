# app/services/agreement_service.py
# 교육 서비스 이용 계약서 - 전자서명 비즈니스 로직

import hashlib
from datetime import datetime
from app.database import execute_query


# 전자서명 적용 기준일 (이 날짜 이후 가입자만 서명 필요)
AGREEMENT_CUTOFF_DATE = "2026-03-15"


def get_active_template() -> dict | None:
    """현재 활성화된 계약서 템플릿 조회"""
    return execute_query(
        "SELECT id, version, title, content, course_type, created_at "
        "FROM agreement_templates "
        "WHERE is_active = 1 "
        "ORDER BY created_at DESC LIMIT 1",
        fetch="one"
    )


def check_student_signed(mem_mbr_id: str, template_id: int) -> bool:
    """해당 수강생이 이미 서명했는지 확인"""
    row = execute_query(
        "SELECT COUNT(*) AS cnt FROM agreement_signatures "
        "WHERE mem_MbrId = ? AND template_id = ? AND is_valid = 1",
        (mem_mbr_id, template_id),
        fetch="one"
    )
    return row and row["cnt"] > 0


def needs_agreement(mem_mbr_id: str) -> bool:
    """수강생이 전자서명이 필요한지 판단
    - 2026-03-15 이후 가입자만 대상
    - 활성 수강권이 있어야 대상
    - 이미 서명했으면 불필요
    """
    # 1+2. 가입일 + 활성 수강권을 한 번에 확인
    row = execute_query(
        "SELECT M.mem_edate, "
        "(SELECT COUNT(*) FROM ek_Settlement "
        " WHERE settle_mbr_id = M.mem_MbrId AND settle_state = 1) AS has_settle "
        "FROM ek_Member M WHERE M.mem_MbrId = ?",
        (mem_mbr_id,),
        fetch="one"
    )
    if not row or not row.get("mem_edate"):
        return False

    join_date = str(row["mem_edate"])[:10]
    if join_date < AGREEMENT_CUTOFF_DATE:
        return False

    if not row.get("has_settle"):
        return False

    # 3+4. 활성 계약서 + 서명 여부를 한 번에 확인
    check = execute_query(
        "SELECT T.id, "
        "(SELECT COUNT(*) FROM agreement_signatures "
        " WHERE mem_MbrId = ? AND template_id = T.id AND is_valid = 1) AS signed_cnt "
        "FROM agreement_templates T "
        "WHERE T.is_active = 1 "
        "ORDER BY T.created_at DESC LIMIT 1",
        (mem_mbr_id,),
        fetch="one"
    )
    if not check:
        return False

    return check.get("signed_cnt", 0) == 0


def compute_document_hash(content: str) -> str:
    """계약서 내용의 SHA-256 해시 (무결성 검증용)"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_signature(
    mem_mbr_id: str,
    template_id: int,
    signature_image: str,
    ip_address: str,
    user_agent: str,
    device_info: str,
    document_hash: str,
) -> int:
    """전자서명 저장"""
    return execute_query(
        "INSERT INTO agreement_signatures "
        "(mem_MbrId, template_id, signature_image, agreed_at, "
        "ip_address, user_agent, device_info, document_hash, is_valid) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            mem_mbr_id, template_id, signature_image,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ip_address, user_agent, device_info, document_hash,
        ),
        fetch="rowcount",
    )


def get_signature_history(mem_mbr_id: str) -> list:
    """수강생의 서명 이력 조회 (서명 이미지 포함)"""
    return execute_query(
        "SELECT s.id, s.agreed_at, s.ip_address, s.device_info, "
        "s.signature_image, "
        "t.version, t.title, t.course_type "
        "FROM agreement_signatures s "
        "JOIN agreement_templates t ON s.template_id = t.id "
        "WHERE s.mem_MbrId = ? AND s.is_valid = 1 "
        "ORDER BY s.agreed_at DESC",
        (mem_mbr_id,),
        fetch="all"
    )


def detect_device(user_agent: str) -> str:
    """User-Agent로 디바이스 유형 판별"""
    ua = user_agent.lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "모바일"
    elif "tablet" in ua or "ipad" in ua:
        return "태블릿"
    return "데스크톱"
