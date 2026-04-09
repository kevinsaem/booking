# app/database.py
# 데이터베이스 연결 관리 (듀얼 모드)
#
# DB_MODE=development → SQLite (로컬 개발, Mock 데이터)
# DB_MODE=production  → MS-SQL (kevinsaem.com 실서버, 커넥션 풀)

import sqlite3
import os
import re
import queue
import threading
from contextlib import contextmanager
from app.config import settings

DB_MODE = settings.DB_MODE
print(f"🔧 DB_MODE = {DB_MODE} (from settings)")

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev.db")

# ── MS-SQL 커넥션 풀 설정 ──
POOL_MIN_SIZE = 2
POOL_MAX_SIZE = 5
_pool: queue.Queue = queue.Queue(maxsize=POOL_MAX_SIZE)
_pool_lock = threading.Lock()
_pool_created = 0  # 현재까지 생성된 연결 수


def _get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _build_mssql_conn_str() -> str:
    """MS-SQL 연결 문자열 생성 (풀 내부에서 사용)"""
    import pyodbc
    drivers = [d for d in pyodbc.drivers() if 'SQL Server' in d]
    driver = drivers[0] if drivers else 'ODBC Driver 18 for SQL Server'
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={settings.DB_SERVER};"
        f"DATABASE={settings.DB_NAME};"
        f"UID={settings.DB_USER};"
        f"PWD={settings.DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )


def _create_mssql_conn():
    """새 MS-SQL 연결 생성"""
    import pyodbc
    conn_str = _build_mssql_conn_str()
    conn = pyodbc.connect(conn_str, timeout=10)
    return conn


def _get_mssql_conn():
    """호환성을 위해 유지 - 풀 밖에서 단독 연결이 필요할 때"""
    return _create_mssql_conn()


def _is_conn_alive(conn) -> bool:
    """연결이 살아있는지 확인 (가벼운 쿼리로 테스트)"""
    try:
        conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def _pool_get():
    """풀에서 유효한 연결을 꺼냄. 없으면 새로 생성."""
    global _pool_created

    # 1) 풀에 대기 중인 연결이 있으면 꺼내기 (죽은 연결은 버리고 반복)
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            break
        if _is_conn_alive(conn):
            return conn
        # 죽은 연결 → 닫고 카운터 감소
        try:
            conn.close()
        except Exception:
            pass
        with _pool_lock:
            _pool_created = max(0, _pool_created - 1)

    # 2) 새 연결 생성 가능하면 생성
    can_create = False
    with _pool_lock:
        if _pool_created < POOL_MAX_SIZE:
            _pool_created += 1
            can_create = True

    if can_create:
        try:
            conn = _create_mssql_conn()
            print(f"🔌 MS-SQL 새 연결 생성 (풀 크기: {_pool_created})")
            return conn
        except Exception as e:
            with _pool_lock:
                _pool_created = max(0, _pool_created - 1)
            raise

    # 3) 최대 초과 → 풀에서 반환될 때까지 대기 (최대 30초)
    try:
        conn = _pool.get(timeout=30)
        if _is_conn_alive(conn):
            return conn
        try:
            conn.close()
        except Exception:
            pass
        with _pool_lock:
            _pool_created = max(0, _pool_created - 1)
        # 죽은 연결이었으면 새로 생성
        conn = _create_mssql_conn()
        with _pool_lock:
            _pool_created += 1
        return conn
    except queue.Empty:
        raise ConnectionError("MS-SQL 커넥션 풀 대기 시간 초과 (30초)")


def _pool_return(conn):
    """연결을 풀에 반환. 풀이 가득 차면 닫음."""
    global _pool_created
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        # 풀이 가득 → 연결 닫기
        try:
            conn.close()
        except Exception:
            pass
        with _pool_lock:
            _pool_created = max(0, _pool_created - 1)


def _pool_init():
    """풀 초기화: 최소 크기만큼 연결 미리 생성"""
    global _pool_created
    for _ in range(POOL_MIN_SIZE):
        try:
            conn = _create_mssql_conn()
            _pool.put_nowait(conn)
            with _pool_lock:
                _pool_created += 1
        except Exception as e:
            print(f"⚠️ 풀 초기화 중 연결 실패 (무시하고 계속): {e}")


def _pool_close():
    """풀 내 모든 연결 닫기"""
    global _pool_created
    closed = 0
    while not _pool.empty():
        try:
            conn = _pool.get_nowait()
            conn.close()
            closed += 1
        except (queue.Empty, Exception):
            pass
    with _pool_lock:
        _pool_created = 0
    if closed:
        print(f"🔌 MS-SQL 커넥션 풀 정리 완료 ({closed}개 연결 닫음)")


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
            _pool_init()
            print(f"✅ MS-SQL 커넥션 풀 초기화 완료 (min={POOL_MIN_SIZE}, max={POOL_MAX_SIZE}, server={settings.DB_SERVER})")
        except Exception as e:
            print(f"❌ MS-SQL 풀 초기화 실패: {e}")


async def close_db():
    if DB_MODE != "development":
        _pool_close()


@contextmanager
def get_db():
    if DB_MODE == "development":
        conn = _get_sqlite_conn()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = _pool_get()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            _pool_return(conn)


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


def _convert_row(d: dict) -> dict:
    """MS-SQL datetime 객체를 문자열로 자동 변환"""
    from datetime import datetime as dt, date as d_date
    for k, v in d.items():
        if isinstance(v, dt):
            d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, d_date):
            d[k] = v.strftime("%Y-%m-%d")
    return d


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
                return [_convert_row(dict(zip(cols, r))) for r in cursor.fetchall()]
            elif fetch == "one":
                if DB_MODE == "development":
                    row = cursor.fetchone()
                    return dict(row) if row else None
                if cursor.description:
                    cols = [d[0] for d in cursor.description]
                    row = cursor.fetchone()
                    return _convert_row(dict(zip(cols, row))) if row else None
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
