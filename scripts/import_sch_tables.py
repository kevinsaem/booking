#!/usr/bin/env python3
"""
scripts/import_sch_tables.py
ek_Sch 관련 테이블 CSV → SQLite 임포트 (2026-03-20 이후 데이터만)

CSV 파일 위치: /Users/kevin/Documents/project/db_backup/
대상 DB: dev.db (프로젝트 루트)

사용법:
  source venv/bin/activate
  python scripts/import_sch_tables.py
"""

import sys
import os
import csv
import sqlite3
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.database import SQLITE_PATH

CSV_DIR = "/Users/kevin/Documents/project/db_backup"
DATE_CUTOFF = "2026-03-20"


def safe_text(val):
    """빈 문자열/NULL을 None으로 변환"""
    if val is None or str(val).strip() == "" or str(val).strip().lower() == "null":
        return None
    return str(val).strip()


def create_table(conn, table_name: str, columns: list[str]):
    """모든 컬럼을 TEXT 타입으로 테이블 생성"""
    cols_def = ", ".join(f'"{c}" TEXT' for c in columns)
    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.execute(f"CREATE TABLE {table_name} ({cols_def})")
    conn.commit()
    print(f"  테이블 생성: {table_name} ({len(columns)}개 컬럼)")


def import_ek_sch(conn):
    """ek_Sch 임포트 - sch_e_date >= 2026-03-20"""
    print("\n[1/4] ek_Sch 임포트...")
    filepath = os.path.join(CSV_DIR, "dbo_ek_Sch.csv")
    if not os.path.exists(filepath):
        print("  [경고] 파일 없음")
        return

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        create_table(conn, "ek_Sch", columns)

        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO ek_Sch VALUES ({placeholders})'

        count = 0
        skipped = 0
        for row in reader:
            sch_e_date = safe_text(row.get("sch_e_date"))
            # sch_e_date가 없거나 cutoff 이전이면 스킵
            if not sch_e_date or sch_e_date < DATE_CUTOFF:
                skipped += 1
                continue
            values = tuple(safe_text(row[c]) for c in columns)
            conn.execute(sql, values)
            count += 1

        conn.commit()
        print(f"  완료: {count}건 삽입, {skipped}건 필터링됨")


def import_ek_sch_day(conn):
    """ek_Sch_Day 임포트 - sch_day_lec_date >= 2026-03-20"""
    print("\n[2/4] ek_Sch_Day 임포트...")
    filepath = os.path.join(CSV_DIR, "dbo_ek_Sch_Day.csv")
    if not os.path.exists(filepath):
        print("  [경고] 파일 없음")
        return

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        create_table(conn, "ek_Sch_Day", columns)

        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO ek_Sch_Day VALUES ({placeholders})'

        count = 0
        skipped = 0
        for row in reader:
            lec_date = safe_text(row.get("sch_day_lec_date"))
            if not lec_date or lec_date < DATE_CUTOFF:
                skipped += 1
                continue
            values = tuple(safe_text(row[c]) for c in columns)
            conn.execute(sql, values)
            count += 1

        conn.commit()
        print(f"  완료: {count}건 삽입, {skipped}건 필터링됨")


def import_ek_sch_detail(conn):
    """ek_Sch_Detail 임포트 - sch_detail_lec_date >= 2026-03-20
    1.1GB 파일이므로 한 줄씩 읽어서 처리"""
    print("\n[3/4] ek_Sch_Detail 임포트 (대용량 1.1GB, 줄 단위 처리)...")
    filepath = os.path.join(CSV_DIR, "dbo_ek_Sch_Detail.csv")
    if not os.path.exists(filepath):
        print("  [경고] 파일 없음")
        return

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        # BOM 제거 (혹시 남아있을 경우)
        header[0] = header[0].lstrip("\ufeff")
        columns = [c.strip() for c in header]

        create_table(conn, "ek_Sch_Detail", columns)

        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO ek_Sch_Detail VALUES ({placeholders})'

        # sch_detail_lec_date 컬럼 인덱스 찾기
        try:
            date_idx = columns.index("sch_detail_lec_date")
        except ValueError:
            print("  [에러] sch_detail_lec_date 컬럼을 찾을 수 없음")
            return

        count = 0
        skipped = 0
        total_read = 0
        errors = 0

        for row in reader:
            total_read += 1

            if total_read % 100000 == 0:
                print(f"  ... {total_read:,}행 읽음, {count:,}건 삽입, {skipped:,}건 스킵")

            # 컬럼 수 불일치 처리
            if len(row) != len(columns):
                errors += 1
                if errors <= 3:
                    print(f"  [경고] {total_read}행 컬럼 수 불일치: {len(row)} vs {len(columns)}")
                continue

            lec_date = row[date_idx].strip() if row[date_idx] else ""
            # 날짜 필터: 앞 10자만 비교 (datetime 형식일 수 있음)
            if not lec_date or lec_date[:10] < DATE_CUTOFF:
                skipped += 1
                continue

            values = tuple(safe_text(v) for v in row)
            try:
                conn.execute(sql, values)
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  [에러] {total_read}행: {e}")

            # 10000건마다 커밋
            if count % 10000 == 0 and count > 0:
                conn.commit()
                print(f"  진행: {count:,}건 삽입됨")

        conn.commit()
        print(f"  완료: {count:,}건 삽입, {skipped:,}건 필터링, {errors}건 에러, 총 {total_read:,}행 읽음")


def import_ek_sch_cal(conn):
    """ek_sch_cal 임포트 - s_date >= 2026-03-20 or e_date >= 2026-03-20"""
    print("\n[4/4] ek_sch_cal 임포트...")
    filepath = os.path.join(CSV_DIR, "dbo_ek_sch_cal.csv")
    if not os.path.exists(filepath):
        print("  [경고] 파일 없음")
        return

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        create_table(conn, "ek_sch_cal", columns)

        placeholders = ", ".join(["?"] * len(columns))
        sql = f'INSERT INTO ek_sch_cal VALUES ({placeholders})'

        count = 0
        skipped = 0
        for row in reader:
            s_date = safe_text(row.get("s_date"))
            e_date = safe_text(row.get("e_date"))

            # s_date 또는 e_date 중 하나라도 cutoff 이후면 포함
            s_ok = s_date and s_date[:10] >= DATE_CUTOFF
            e_ok = e_date and e_date[:10] >= DATE_CUTOFF

            if not (s_ok or e_ok):
                skipped += 1
                continue

            values = tuple(safe_text(row[c]) for c in columns)
            conn.execute(sql, values)
            count += 1

        conn.commit()
        print(f"  완료: {count}건 삽입, {skipped}건 필터링됨")


def print_summary(conn):
    """최종 데이터 수 출력"""
    tables = ["ek_Sch", "ek_Sch_Day", "ek_Sch_Detail", "ek_sch_cal"]
    print("\n" + "=" * 50)
    print("ek_Sch 관련 테이블 임포트 결과")
    print("=" * 50)
    print(f"{'테이블':<25} {'레코드 수':>10}")
    print("-" * 50)
    for table in tables:
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"{table:<25} {count:>10,}")
        except Exception:
            print(f"{table:<25} {'(없음)':>10}")
    print("-" * 50)


def verify_kevin_data(conn):
    """Kevin(C) / cybert1 데이터 확인"""
    print("\n" + "=" * 50)
    print("Kevin(C) / cybert1 ek_Sch_Detail 데이터 확인")
    print(f"(sch_detail_lec_date >= '{DATE_CUTOFF}')")
    print("=" * 50)
    try:
        cur = conn.execute("""
            SELECT sch_detail_code, sch_detail_teach_id, sch_detail_lec_date,
                   sch_detail_Stime, sch_detail_Etime, sch_detail_state,
                   mem_mbrid
            FROM ek_Sch_Detail
            WHERE (sch_detail_teach_id LIKE '%cybert%'
                   OR mem_mbrid LIKE '%cybert%')
            ORDER BY sch_detail_lec_date
            LIMIT 20
        """)
        rows = cur.fetchall()
        if rows:
            print(f"\n  총 {len(rows)}건 (최대 20건 표시):")
            for r in rows:
                print(f"  code={r[0]}, teacher={r[1]}, date={r[2]}, "
                      f"time={r[3]}~{r[4]}, state={r[5]}, member={r[6]}")
        else:
            print("  cybert 관련 데이터 없음")

        # 전체 건수
        cur2 = conn.execute("""
            SELECT COUNT(*) FROM ek_Sch_Detail
            WHERE sch_detail_teach_id LIKE '%cybert%'
               OR mem_mbrid LIKE '%cybert%'
        """)
        total = cur2.fetchone()[0]
        print(f"\n  cybert 관련 전체: {total}건")

    except Exception as e:
        print(f"  [에러] 조회 실패: {e}")


def main():
    start = datetime.now()
    print("=" * 50)
    print("ek_Sch 관련 테이블 CSV → SQLite 임포트")
    print(f"날짜 필터: >= {DATE_CUTOFF}")
    print(f"CSV 경로: {CSV_DIR}")
    print(f"DB 경로:  {SQLITE_PATH}")
    print("=" * 50)

    if not os.path.exists(SQLITE_PATH):
        print("\n[에러] dev.db가 없습니다. 먼저 import_csv.py를 실행하세요.")
        sys.exit(1)

    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    import_ek_sch(conn)
    import_ek_sch_day(conn)
    import_ek_sch_detail(conn)
    import_ek_sch_cal(conn)

    print_summary(conn)
    verify_kevin_data(conn)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n소요 시간: {elapsed:.1f}초")
    print("임포트 완료!")

    conn.close()


if __name__ == "__main__":
    main()
