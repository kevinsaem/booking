"""
3개 테이블 CSV → SQLite 임포트
- ek_WbLevel (648 rows)
- ek_LectureDe (71,286 rows)
- ek_tdplan (125,941 rows)
"""

import csv
import sys
import os

# 큰 필드 대응
csv.field_size_limit(10 * 1024 * 1024)

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db

CSV_DIR = "/Users/kevin/Documents/project/db_backup"


def import_table(table_name: str, csv_filename: str, columns: list[str]):
    csv_path = os.path.join(CSV_DIR, csv_filename)
    print(f"\n{'='*50}")
    print(f"임포트: {table_name} ← {csv_filename}")

    with get_db() as conn:
        # 테이블 생성 (DROP IF EXISTS)
        col_defs = ", ".join(f"{c} TEXT" for c in columns)
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(f"CREATE TABLE {table_name} ({col_defs})")
        conn.commit()
        print(f"  테이블 생성 완료: {len(columns)}개 컬럼")

        # CSV 읽기 + INSERT
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        count = 0
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch = []
            for row in reader:
                values = tuple(row.get(c, "") or "" for c in columns)
                batch.append(values)
                count += 1
                if len(batch) >= 1000:
                    conn.executemany(insert_sql, batch)
                    batch = []
                    if count % 10000 == 0:
                        print(f"  진행: {count:,}행...")
            if batch:
                conn.executemany(insert_sql, batch)
            conn.commit()

        print(f"  완료: {count:,}행 임포트됨")

    return count


def verify():
    """임포트 결과 검증"""
    print(f"\n{'='*50}")
    print("검증 쿼리:")
    with get_db() as conn:
        for table in ["ek_WbLevel", "ek_LectureDe", "ek_tdplan"]:
            row = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()
            print(f"  {table}: {row['cnt']:,}행")

        # 테스트: tdplan → WbLevel → LectureDe JOIN
        test = conn.execute(
            "SELECT COUNT(*) AS cnt FROM ek_tdplan A "
            "JOIN ek_WbLevel B ON A.wb_level_idx = B.wb_level_idx "
            "JOIN ek_LectureDe C ON C.lecturede_idx = A.lecturede_idx"
        ).fetchone()
        print(f"  3-way JOIN 결과: {test['cnt']:,}행")


if __name__ == "__main__":
    # ek_WbLevel
    import_table("ek_WbLevel", "dbo_ek_WbLevel.csv", [
        "wb_level_idx", "wb_code", "wb_level_title", "wb_level_code",
        "wb_level_status", "wb_link", "wb_level_img", "code", "seat_status",
        "wb_level_sumary"
    ])

    # ek_LectureDe
    import_table("ek_LectureDe", "dbo_ek_LectureDe.csv", [
        "lecturede_idx", "lec_idx", "sch_detail_code", "student_id",
        "clsp_idx", "report", "w_date", "fcnt", "ttopic", "nplan",
        "mphoto", "blogurl", "advice", "padvice", "webbook_idx", "ctype",
        "awhen", "awhere", "awho", "awhy", "ahow", "awhat",
        "stime", "ftime", "fdate", "alrimtalk"
    ])

    # ek_tdplan
    import_table("ek_tdplan", "dbo_ek_tdplan.csv", [
        "tsc_idx", "lecturede_idx", "wb_level_idx", "stime", "ftime",
        "gaptime", "memo", "wdate", "notice", "fdate"
    ])

    verify()
    print("\n전체 임포트 완료!")
