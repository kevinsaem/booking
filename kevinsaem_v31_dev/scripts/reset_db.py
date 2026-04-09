#!/usr/bin/env python3
# scripts/reset_db.py
# 개발 DB 초기화 스크립트
#
# 사용법:
#   python scripts/reset_db.py          → DB 리셋 + seed
#   python scripts/reset_db.py --check  → 현재 데이터 확인
#   python scripts/reset_db.py --stats  → 통계 출력

import sys
import os
import sqlite3

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dev.db")


def check_db():
    """현재 DB 상태 확인"""
    if not os.path.exists(DB_PATH):
        print("❌ dev.db 파일이 없습니다. --reset으로 생성하세요.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    tables = [
        "ek_EduCenter", "ek_Member", "ek_Package",
        "ek_Settlement", "ek_Sch_Detail_Room",
        "ek_Sch_Detail_Room_mem", "dev_messages", "dev_notices"
    ]

    print(f"📂 DB 파일: {DB_PATH}")
    print(f"📏 크기: {os.path.getsize(DB_PATH) / 1024:.1f} KB\n")
    print(f"{'테이블':<30} {'레코드 수':>10}")
    print("-" * 42)

    for table in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            count = c.fetchone()[0]
            print(f"{table:<30} {count:>10}")
        except Exception:
            print(f"{table:<30} {'(없음)':>10}")

    conn.close()


def show_stats():
    """상세 통계"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("\n👤 수강생 목록:")
    c.execute("SELECT mem_MbrId, mem_MbrName, injeung_code FROM ek_Member WHERE mem_MbrType='student'")
    for r in c.fetchall():
        print(f"  {r['mem_MbrId']} | {r['mem_MbrName']} | 인증: {r['injeung_code']}")

    print("\n👨‍🏫 강사 목록:")
    c.execute("SELECT mem_MbrId, mem_MbrName FROM ek_Member WHERE mem_MbrType='teacher'")
    for r in c.fetchall():
        print(f"  {r['mem_MbrId']} | {r['mem_MbrName']}")

    print("\n📦 패키지:")
    c.execute("SELECT * FROM ek_Package")
    for r in c.fetchall():
        print(f"  [{r['package_code']}] {r['package_name']} - {r['class_cnt']}회 - {r['price']:,}원")

    print("\n📅 향후 슬롯 수:")
    c.execute("SELECT COUNT(*) FROM ek_Sch_Detail_Room WHERE sch_detail_Stime >= datetime('now','localtime')")
    print(f"  {c.fetchone()[0]}개")

    print("\n📋 김수강(STU001) 잔여 수업:")
    c.execute("""
        SELECT P.class_cnt - COUNT(R.idx) AS remaining
        FROM ek_Settlement S
        JOIN ek_Package P ON S.settle_package_code = P.package_code
        LEFT JOIN ek_Sch_Detail_Room_mem R ON R.settle_code = S.settle_code AND R.status = 1
        WHERE S.settle_code = 10001 AND S.settle_state = 1
        GROUP BY P.class_cnt
    """)
    row = c.fetchone()
    print(f"  {row['remaining']}회" if row else "  조회 실패")

    conn.close()


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_db()
    elif "--stats" in sys.argv:
        check_db()
        show_stats()
    else:
        # 리셋
        from app.seed import reset_db
        reset_db()
        print()
        check_db()
        show_stats()
