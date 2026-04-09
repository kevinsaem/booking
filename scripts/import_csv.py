#!/usr/bin/env python3
"""
scripts/import_csv.py
MS-SQL 백업 CSV → SQLite 개발 DB 임포트

CSV 파일 위치: /Users/kevin/Documents/project/db_backup/
대상 DB: dev.db (프로젝트 루트)

사용법:
  source venv/bin/activate
  python scripts/import_csv.py
"""

import sys
import os
import csv
import sqlite3
from datetime import datetime

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.seed import init_sqlite_tables
from app.database import SQLITE_PATH

CSV_DIR = "/Users/kevin/Documents/project/db_backup"
BATCH_SIZE = 1000


def read_csv(filename: str) -> list[dict]:
    """CSV 파일을 읽어서 dict 리스트로 반환 (BOM 처리)"""
    filepath = os.path.join(CSV_DIR, filename)
    if not os.path.exists(filepath):
        print(f"  [경고] 파일 없음: {filename}")
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def safe_int(val, default=0) -> int:
    """float 문자열(예: '140000.0')이나 빈 값을 int로 변환"""
    if val is None or str(val).strip() == "":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_text(val, default=None) -> str | None:
    """빈 문자열/NULL을 None으로 변환"""
    if val is None or str(val).strip() == "" or str(val).strip().lower() == "null":
        return default
    return str(val).strip()


def batch_insert(conn, sql: str, rows: list[tuple], table_name: str) -> tuple[int, int]:
    """배치 삽입. (성공 수, 실패 수) 반환"""
    c = conn.cursor()
    success = 0
    errors = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        for row in batch:
            try:
                c.execute(sql, row)
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [에러] {table_name} row 스킵: {e}")
                    print(f"         데이터: {row[:3]}...")
                elif errors == 4:
                    print(f"  [에러] {table_name} 추가 에러 생략...")
        conn.commit()
    return success, errors


def import_edu_center(conn) -> None:
    """ek_EduCenter 임포트"""
    print("\n[1/6] ek_EduCenter 임포트...")
    rows_raw = read_csv("dbo_ek_EduCenter.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        rows.append((
            safe_int(r.get("edc_Idx")),
            safe_text(r.get("edc_Name"), "이름없음"),
        ))

    sql = "INSERT OR REPLACE INTO ek_EduCenter (edc_Idx, edc_Name) VALUES (?, ?)"
    ok, err = batch_insert(conn, sql, rows, "ek_EduCenter")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def import_member(conn) -> None:
    """ek_Member 임포트 (mem_Edate → mem_edate 매핑)"""
    print("\n[2/6] ek_Member 임포트...")
    rows_raw = read_csv("dbo_ek_Member.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        mem_id = safe_text(r.get("mem_MbrId"))
        if not mem_id:
            continue
        rows.append((
            mem_id,
            safe_text(r.get("mem_MbrName"), "이름없음"),
            safe_text(r.get("mem_nickname")),
            safe_text(r.get("mem_MbrImg")),
            safe_text(r.get("mem_TelNo3")),
            safe_text(r.get("mem_MbrType")),
            safe_text(r.get("mem_Edate")),       # CSV: mem_Edate → SQLite: mem_edate
            safe_text(r.get("injeung_code")),
            safe_int(r.get("edc_idx"), 0),
        ))

    sql = """INSERT OR REPLACE INTO ek_Member
        (mem_MbrId, mem_MbrName, mem_nickname, mem_MbrImg, mem_TelNo3,
         mem_MbrType, mem_edate, injeung_code, edc_idx)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    ok, err = batch_insert(conn, sql, rows, "ek_Member")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def import_package(conn) -> None:
    """ek_Package 임포트 (price float→int)"""
    print("\n[3/6] ek_Package 임포트...")
    rows_raw = read_csv("dbo_ek_Package.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        rows.append((
            safe_int(r.get("package_code")),
            safe_text(r.get("package_name"), "이름없음"),
            safe_int(r.get("class_cnt"), 0),
            safe_int(r.get("lec_time"), 50),
            safe_int(r.get("month_cnt"), 1),
            safe_int(r.get("price"), 0),          # float → int
        ))

    sql = """INSERT OR REPLACE INTO ek_Package
        (package_code, package_name, class_cnt, lec_time, month_cnt, price)
        VALUES (?, ?, ?, ?, ?, ?)"""
    ok, err = batch_insert(conn, sql, rows, "ek_Package")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def import_settlement(conn) -> None:
    """ek_Settlement 임포트 (settle_Sdate→settle_sdate, settle_Edate→settle_edate, amount float→int)"""
    print("\n[4/6] ek_Settlement 임포트...")
    rows_raw = read_csv("dbo_ek_Settlement.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        settle_mbr_id = safe_text(r.get("settle_mbr_id"))
        if not settle_mbr_id:
            continue
        rows.append((
            safe_int(r.get("settle_code")),
            settle_mbr_id,
            safe_int(r.get("settle_package_code"), 0),
            safe_int(r.get("settle_amount"), 0),   # float → int
            safe_int(r.get("settle_state"), 1),
            safe_text(r.get("settle_date")),
            safe_text(r.get("settle_Sdate")),      # CSV: settle_Sdate → SQLite: settle_sdate
            safe_text(r.get("settle_Edate")),      # CSV: settle_Edate → SQLite: settle_edate
        ))

    sql = """INSERT OR REPLACE INTO ek_Settlement
        (settle_code, settle_mbr_id, settle_package_code, settle_amount,
         settle_state, settle_date, settle_sdate, settle_edate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    ok, err = batch_insert(conn, sql, rows, "ek_Settlement")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def import_sch_detail_room(conn) -> None:
    """ek_Sch_Detail_Room 임포트 (edc_idx는 CSV에 없으므로 기본값 0)"""
    print("\n[5/6] ek_Sch_Detail_Room 임포트...")
    rows_raw = read_csv("dbo_ek_Sch_Detail_Room.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        rows.append((
            safe_int(r.get("sch_room_idx")),
            safe_text(r.get("sch_teach_id"), ""),
            safe_text(r.get("sch_detail_Stime"), ""),
            safe_text(r.get("sch_detail_Etime"), ""),
            safe_int(r.get("sch_room_status"), 1),
            0,  # edc_idx: CSV에 없으므로 기본값 0
        ))

    sql = """INSERT OR REPLACE INTO ek_Sch_Detail_Room
        (sch_room_idx, sch_teach_id, sch_detail_Stime, sch_detail_Etime,
         sch_room_status, edc_idx)
        VALUES (?, ?, ?, ?, ?, ?)"""
    ok, err = batch_insert(conn, sql, rows, "ek_Sch_Detail_Room")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def import_sch_detail_room_mem(conn) -> None:
    """ek_Sch_Detail_Room_mem 임포트 (필요한 컬럼만)"""
    print("\n[6/6] ek_Sch_Detail_Room_mem 임포트...")
    rows_raw = read_csv("dbo_ek_Sch_Detail_Room_mem.csv")
    if not rows_raw:
        return

    rows = []
    for r in rows_raw:
        rows.append((
            safe_int(r.get("idx")),
            safe_int(r.get("sch_room_idx")),
            safe_text(r.get("mem_mbrid"), ""),
            safe_int(r.get("settle_code"), 0),
            safe_text(r.get("l_s_date")),
            safe_text(r.get("l_f_date")),
            safe_int(r.get("status"), 1),
            safe_text(r.get("w_date")),
        ))

    sql = """INSERT OR REPLACE INTO ek_Sch_Detail_Room_mem
        (idx, sch_room_idx, mem_mbrid, settle_code,
         l_s_date, l_f_date, status, w_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    ok, err = batch_insert(conn, sql, rows, "ek_Sch_Detail_Room_mem")
    print(f"  완료: {ok}건 삽입, {err}건 실패")


def seed_kakao_test_accounts(conn) -> None:
    """카카오 테스트 계정 시딩 (admin + 강사 3명)"""
    print("\n[추가] 카카오 테스트 계정 시딩...")
    c = conn.cursor()
    accounts = [
        ("admin_test", "ADM001", "관리자", "admin"),
        ("teacher_test_1", "TEA001", "김코딩", "teacher"),
        ("teacher_test_2", "TEA002", "박데이터", "teacher"),
        ("teacher_test_3", "TEA003", "이웹개발", "teacher"),
    ]

    # 실데이터에 ADM001, TEA001~003이 없을 수 있으므로
    # ek_Member에 없으면 먼저 추가
    admin_teachers = [
        ("ADM001", "관리자", "관리자", None, "01099999999", "admin", None, "0000", 1),
        ("TEA001", "김코딩", "김코딩", None, "01098765432", "4", None, "1111", 1),
        ("TEA002", "박데이터", "박데이터", None, "01087654321", "4", None, "2222", 1),
        ("TEA003", "이웹개발", "이웹개발", None, "01076543210", "4", None, "3333", 1),
    ]
    for member in admin_teachers:
        c.execute("SELECT COUNT(*) FROM ek_Member WHERE mem_MbrId = ?", (member[0],))
        if c.fetchone()[0] == 0:
            c.execute(
                "INSERT INTO ek_Member VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                member
            )
            print(f"  ek_Member에 테스트 계정 추가: {member[0]} ({member[1]})")

    for kakao_id, mem_id, nickname, role in accounts:
        c.execute(
            "INSERT OR REPLACE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
            (kakao_id, mem_id, nickname, role)
        )
    conn.commit()
    print(f"  완료: {len(accounts)}개 테스트 계정 등록")


def print_summary(conn) -> None:
    """최종 데이터 수 출력"""
    c = conn.cursor()
    tables = [
        "ek_EduCenter", "ek_Member", "ek_Package",
        "ek_Settlement", "ek_Sch_Detail_Room",
        "ek_Sch_Detail_Room_mem",
        "dev_messages", "dev_notices", "dev_lesson_history",
        "kakao_members", "dev_class_memos",
    ]
    print("\n" + "=" * 45)
    print("최종 데이터 현황")
    print("=" * 45)
    print(f"{'테이블':<30} {'레코드 수':>10}")
    print("-" * 45)
    for table in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            count = c.fetchone()[0]
            print(f"{table:<30} {count:>10}")
        except Exception:
            print(f"{table:<30} {'(없음)':>10}")
    print("-" * 45)
    db_size = os.path.getsize(SQLITE_PATH) / 1024
    print(f"DB 파일 크기: {db_size:.1f} KB")


def main():
    start = datetime.now()
    print("=" * 45)
    print("CSV → SQLite 임포트 시작")
    print(f"CSV 경로: {CSV_DIR}")
    print(f"DB 경로:  {SQLITE_PATH}")
    print("=" * 45)

    # 1. 기존 DB 삭제 후 테이블 생성
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        print("\n기존 dev.db 삭제")

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # 임포트 중 FK 끄기 (순서 무관하게)

    print("테이블 생성 (init_sqlite_tables)...")
    init_sqlite_tables(conn)

    # 2. CSV 데이터 임포트
    import_edu_center(conn)
    import_member(conn)
    import_package(conn)
    import_settlement(conn)
    import_sch_detail_room(conn)
    import_sch_detail_room_mem(conn)

    # 3. 카카오 테스트 계정 시딩
    seed_kakao_test_accounts(conn)

    # 4. FK 다시 활성화
    conn.execute("PRAGMA foreign_keys=ON")

    # 5. 최종 현황
    print_summary(conn)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n소요 시간: {elapsed:.1f}초")
    print("임포트 완료!")

    conn.close()


if __name__ == "__main__":
    main()
