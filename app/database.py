# app/database.py
# 데이터베이스 연결 관리 (듀얼 모드)
#
# DB_MODE=development → SQLite (로컬 개발, Mock 데이터)
# DB_MODE=production  → MS-SQL (kevinsaem.com 실서버)

import sqlite3
import os
import re
from contextlib import contextmanager
from app.config import settings

DB_MODE = settings.DB_MODE
print(f"🔧 DB_MODE = {DB_MODE} (from settings)")

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev.db")


def _get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_mssql_conn():
    import pyodbc
    # 사용 가능한 SQL Server 드라이버 자동 탐지
    drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    driver = drivers[0] if drivers else 'ODBC Driver 18 for SQL Server'
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_NAME};"
        f"UID={settings.DB_USER};"
        f"PWD={settings.DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


async def init_db():
    if DB_MODE == "development":
        from app.seed import init_sqlite_tables, seed_if_empty
        conn = _get_sqlite_conn()
        init_sqlite_tables(conn)
        seed_if_empty(conn)
        conn.close()
        print(f"✅ SQLite 개발 DB: {SQLITE_PATH}")
    else:
        try:
            conn = _get_mssql_conn()
            conn.close()
            print(f"✅ MS-SQL 연결: {settings.DB_SERVER}")
        except Exception as e:
            print(f"❌ MS-SQL 실패: {e}")


async def close_db():
    pass


@contextmanager
def get_db():
    if DB_MODE == "development":
        conn = _get_sqlite_conn()
    else:
        conn = _get_mssql_conn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _translate_sql(sql: str) -> str:
    """양방향 SQL 변환: development=SQLite, production=MS-SQL"""
    if DB_MODE == "development":
        # MS-SQL → SQLite
        sql = sql.replace("GETDATE()", "datetime('now','localtime')")
        sql = sql.replace("ISNULL(", "COALESCE(")
        sql = re.sub(r"CONVERT\s*\(\s*varchar\s*\(\s*10\s*\)\s*,\s*([^,]+?)\s*,\s*2[31]\s*\)", r"strftime('%Y-%m-%d',\1)", sql)
        sql = re.sub(r"CONVERT\s*\(\s*varchar\s*\(\s*5\s*\)\s*,\s*([^,]+?)\s*,\s*108\s*\)", r"strftime('%H:%M',\1)", sql)
        sql = re.sub(r"YEAR\(([^)]+)\)", r"cast(strftime('%Y',\1) as integer)", sql)
        sql = re.sub(r"MONTH\(([^)]+)\)", r"cast(strftime('%m',\1) as integer)", sql)
        sql = re.sub(r"DATEADD\s*\(\s*hour\s*,\s*9\s*,\s*([^)]+)\)", r"\1", sql)
    else:
        # SQLite → MS-SQL
        sql = re.sub(r"datetime\s*\(\s*'now'\s*,\s*'\+9 hours'\s*\)", "DATEADD(hour, 9, GETDATE())", sql)
        sql = re.sub(r"datetime\s*\(\s*'now'\s*,\s*'localtime'\s*\)", "GETDATE()", sql)
        sql = re.sub(r"datetime\s*\(\s*'now'\s*\)", "GETDATE()", sql)
        sql = re.sub(r"datetime\s*\(\s*([^,)]+?)\s*,\s*'\+9 hours'\s*\)", r"DATEADD(hour, 9, \1)", sql)
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        sql = sql.replace("INSERT OR REPLACE", "UPDATE")
        # LIMIT N → TOP N 변환
        limit_match = re.search(r"\bLIMIT\s+(\d+)\s*$", sql, re.IGNORECASE)
        if limit_match:
            n = limit_match.group(1)
            sql = re.sub(r"\bLIMIT\s+\d+\s*$", "", sql, flags=re.IGNORECASE)
            sql = re.sub(r"^(\s*SELECT\s)", rf"\1TOP {n} ", sql, count=1, flags=re.IGNORECASE)
    return sql


def execute_query(sql: str, params=None, fetch: str = "all"):
    translated = _translate_sql(sql)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(translated, params)
            else:
                cursor.execute(translated)
            if fetch == "all":
                if DB_MODE == "development":
                    return [dict(r) for r in cursor.fetchall()]
                cols = [d[0] for d in cursor.description] if cursor.description else []
                return [dict(zip(cols, r)) for r in cursor.fetchall()]
            elif fetch == "one":
                if DB_MODE == "development":
                    row = cursor.fetchone()
                    return dict(row) if row else None
                if cursor.description:
                    cols = [d[0] for d in cursor.description]
                    row = cursor.fetchone()
                    return dict(zip(cols, row)) if row else None
                return None
            else:
                conn.commit()
                return cursor.rowcount
    except Exception as e:
        print(f"⚠️ DB 쿼리 실패: {e}")
        print(f"  → SQL: {translated[:200]}")
        if fetch == "all":
            return []
        elif fetch == "one":
            return None
        else:
            return 0
