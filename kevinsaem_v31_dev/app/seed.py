# app/seed.py
# SQLite 테이블 생성 + Mock 데이터 시딩
#
# 실서버 MS-SQL의 테이블 구조를 SQLite로 재현합니다.
# 컬럼명, 관계, 비즈니스 로직을 동일하게 유지하여
# 프로덕션 전환 시 SQL 변경을 최소화합니다.
#
# 사용법:
#   from app.seed import init_sqlite_tables, seed_if_empty
#   init_sqlite_tables(conn)
#   seed_if_empty(conn)

from datetime import datetime, timedelta


def init_sqlite_tables(conn):
    """실서버 스키마와 동일한 테이블 구조를 SQLite에 생성"""
    c = conn.cursor()

    # === ek_EduCenter: 캠퍼스 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_EduCenter (
            edc_Idx INTEGER PRIMARY KEY,
            edc_Name TEXT NOT NULL
        )
    """)

    # === ek_Member: 회원 (수강생 + 강사 통합) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_Member (
            mem_MbrId TEXT PRIMARY KEY,
            mem_MbrName TEXT NOT NULL,
            mem_nickname TEXT,
            mem_MbrImg TEXT,
            mem_TelNo3 TEXT,
            mem_MbrType TEXT,
            mem_edate TEXT,
            injeung_code TEXT,
            edc_idx INTEGER,
            FOREIGN KEY (edc_idx) REFERENCES ek_EduCenter(edc_Idx)
        )
    """)

    # === ek_Package: 수강 과정 (상품) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_Package (
            package_code INTEGER PRIMARY KEY,
            package_name TEXT NOT NULL,
            class_cnt INTEGER NOT NULL DEFAULT 0,
            lec_time INTEGER DEFAULT 50,
            month_cnt INTEGER DEFAULT 1,
            price INTEGER DEFAULT 0
        )
    """)

    # === ek_Settlement: 결제 (수강권) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_Settlement (
            settle_code INTEGER PRIMARY KEY AUTOINCREMENT,
            settle_mbr_id TEXT NOT NULL,
            settle_package_code INTEGER NOT NULL,
            settle_amount INTEGER DEFAULT 0,
            settle_state INTEGER DEFAULT 1,
            settle_date TEXT,
            settle_sdate TEXT,
            settle_edate TEXT,
            FOREIGN KEY (settle_mbr_id) REFERENCES ek_Member(mem_MbrId),
            FOREIGN KEY (settle_package_code) REFERENCES ek_Package(package_code)
        )
    """)

    # === ek_Sch_Detail_Room: 수업 슬롯 (관리자 등록) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_Sch_Detail_Room (
            sch_room_idx INTEGER PRIMARY KEY AUTOINCREMENT,
            sch_teach_id TEXT NOT NULL,
            sch_detail_Stime TEXT NOT NULL,
            sch_detail_Etime TEXT NOT NULL,
            sch_room_status INTEGER DEFAULT 1,
            edc_idx INTEGER,
            FOREIGN KEY (sch_teach_id) REFERENCES ek_Member(mem_MbrId),
            FOREIGN KEY (edc_idx) REFERENCES ek_EduCenter(edc_Idx)
        )
    """)

    # === ek_Sch_Detail_Room_mem: 예약 기록 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_Sch_Detail_Room_mem (
            idx INTEGER PRIMARY KEY AUTOINCREMENT,
            sch_room_idx INTEGER NOT NULL,
            mem_mbrid TEXT NOT NULL,
            settle_code INTEGER NOT NULL,
            l_s_date TEXT NOT NULL,
            l_f_date TEXT NOT NULL,
            status INTEGER DEFAULT 1,
            w_date TEXT,
            FOREIGN KEY (sch_room_idx) REFERENCES ek_Sch_Detail_Room(sch_room_idx),
            FOREIGN KEY (mem_mbrid) REFERENCES ek_Member(mem_MbrId),
            FOREIGN KEY (settle_code) REFERENCES ek_Settlement(settle_code)
        )
    """)

    # === 추가 테이블: 메시지 (실서버에는 없지만 개발용) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS dev_messages (
            msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        )
    """)

    # === 추가 테이블: 공지사항 (개발용) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS dev_notices (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            type TEXT DEFAULT 'notice',
            created_at TEXT NOT NULL,
            is_new INTEGER DEFAULT 0
        )
    """)

    conn.commit()


def seed_if_empty(conn):
    """테이블이 비어있으면 Mock 데이터 삽입"""
    c = conn.cursor()

    # 이미 데이터가 있으면 스킵
    c.execute("SELECT COUNT(*) FROM ek_Member")
    if c.fetchone()[0] > 0:
        return

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # ===== 1. 캠퍼스 =====
    c.executemany("INSERT INTO ek_EduCenter VALUES (?, ?)", [
        (1, "안산선부캠퍼스"),
        (2, "안산초지캠퍼스"),
    ])

    # ===== 2. 수강 과정 (패키지) =====
    c.executemany(
        "INSERT INTO ek_Package (package_code, package_name, class_cnt, lec_time, month_cnt, price) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, "취미반 주2회", 8, 50, 1, 210000),
            (102, "진로반 주2회", 20, 50, 2, 290000),
            (103, "월정기 진로반", 40, 50, 1, 450000),
        ]
    )

    # ===== 3. 회원 (수강생 5명 + 강사 3명) =====
    # 수강생
    students = [
        ("STU001", "김수강", "수강이", None, "01012345678", "student", None, "1234", 1),
        ("STU002", "이학생", "학생이", None, "01023456789", "student", None, "5678", 1),
        ("STU003", "박공부", "공부왕", None, "01034567890", "student", None, "9012", 1),
        ("STU004", "최열심", "열심이", None, "01045678901", "student", None, "3456", 2),
        ("STU005", "정성실", "성실이", None, "01056789012", "student", None, "7890", 1),
    ]
    # 강사
    teachers = [
        ("TEA001", "김코딩", "김코딩", None, "01098765432", "teacher", None, None, 1),
        ("TEA002", "박데이터", "박데이터", None, "01087654321", "teacher", None, None, 1),
        ("TEA003", "이웹개발", "이웹개발", None, "01076543210", "teacher", None, None, 1),
    ]
    c.executemany(
        "INSERT INTO ek_Member VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        students + teachers
    )

    # ===== 4. 결제 (수강권) =====
    settle_start = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    settle_end = (now + timedelta(days=40)).strftime("%Y-%m-%d")
    c.executemany(
        "INSERT INTO ek_Settlement (settle_code, settle_mbr_id, settle_package_code, settle_amount, settle_state, settle_date, settle_sdate, settle_edate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (10001, "STU001", 102, 290000, 1, "2026-03-01", settle_start, settle_end),
            (10002, "STU002", 101, 210000, 1, "2026-03-05", settle_start, settle_end),
            (10003, "STU003", 103, 450000, 1, "2026-02-15", "2026-02-15", "2026-05-15"),
            (10004, "STU004", 102, 290000, 1, "2026-03-10", settle_start, settle_end),
            (10005, "STU005", 101, 210000, 1, "2026-03-15", settle_start, settle_end),
        ]
    )

    # ===== 5. 수업 슬롯 (향후 4주, 월~금) =====
    time_patterns = [
        ("10:00", "10:50"),
        ("11:00", "11:50"),
        ("14:00", "14:50"),
        ("15:00", "15:50"),
        ("16:00", "16:50"),
        ("17:00", "17:50"),
    ]
    teacher_assignments = {
        "10:00": ["TEA001", "TEA002"],
        "11:00": ["TEA001"],
        "14:00": ["TEA001", "TEA002", "TEA003"],
        "15:00": ["TEA002", "TEA003"],
        "16:00": ["TEA003"],
        "17:00": ["TEA001", "TEA003"],
    }

    slot_idx = 1000
    for week in range(4):
        for day_offset in range(5):  # 월~금
            date = now + timedelta(days=(7 * week + day_offset - now.weekday()))
            if date.date() < now.date():
                continue  # 과거 날짜 스킵
            date_str = date.strftime("%Y-%m-%d")
            for s_time, e_time in time_patterns:
                for teacher_id in teacher_assignments.get(s_time, []):
                    slot_idx += 1
                    c.execute(
                        "INSERT INTO ek_Sch_Detail_Room (sch_room_idx, sch_teach_id, sch_detail_Stime, sch_detail_Etime, sch_room_status, edc_idx) VALUES (?, ?, ?, ?, 1, 1)",
                        (slot_idx, teacher_id, f"{date_str} {s_time}:00", f"{date_str} {e_time}:00")
                    )

    # ===== 6. 기존 예약 (김수강의 과거 수업 13회) =====
    past_dates = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(1, 28, 2)]
    for i, pdate in enumerate(past_dates[:13]):
        teacher = "TEA001" if i % 2 == 0 else "TEA002"
        c.execute(
            "INSERT INTO ek_Sch_Detail_Room_mem (sch_room_idx, mem_mbrid, settle_code, l_s_date, l_f_date, status, w_date) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (1001 + i, "STU001", 10001, f"{pdate} 14:00:00", f"{pdate} 14:50:00", pdate)
        )

    # ===== 7. 메시지 (강사↔수강생) =====
    c.executemany(
        "INSERT INTO dev_messages (sender_id, receiver_id, content, sent_at, is_read) VALUES (?, ?, ?, ?, ?)",
        [
            ("STU001", "TEA001", "선생님 다음 수업은 어떤 내용인가요?", f"{today} 14:30:00", 1),
            ("TEA001", "STU001", "다음 수업에서는 ChatGPT API를 활용한 프롬프트 엔지니어링을 다룰 예정입니다.", f"{today} 14:35:00", 0),
            ("STU001", "TEA001", "준비물이 있을까요?", f"{today} 14:36:00", 1),
            ("TEA001", "STU001", "OpenAI API 키만 준비해주시면 됩니다. 수업 전에 발급 방법도 안내드릴게요!", f"{today} 14:40:00", 0),
            ("TEA002", "STU001", "과제 확인했습니다. 잘 하셨어요!", f"{(now-timedelta(days=1)).strftime('%Y-%m-%d')} 10:15:00", 1),
        ]
    )

    # ===== 8. 공지사항 =====
    c.executemany(
        "INSERT INTO dev_notices (title, content, type, created_at, is_new) VALUES (?, ?, ?, ?, ?)",
        [
            ("4월 AI활용 특강 안내",
             "ChatGPT, Midjourney, Claude를 활용한 실전 AI 활용법을 배우는 특강이 4월에 진행됩니다. 수강생 여러분의 많은 관심 부탁드립니다.",
             "notice", "2026-03-20", 1),
            ("설 연휴 휴원 안내",
             "2/7(금)~2/11(화) 설 연휴 기간 동안 휴원합니다. 수업은 2/12(수)부터 정상 진행됩니다.",
             "notice", "2026-03-15", 0),
            ("친구 추천 이벤트 - 1회 무료 수업!",
             "성인반 친구를 추천하시면 추천인과 피추천인 모두 1회 무료 수업을 드립니다. 카카오톡으로 문의해주세요.",
             "event", "2026-03-10", 0),
            ("Python 기초 무료 특강 안내",
             "Python을 처음 접하시는 분들을 위한 무료 특강이 3월 마지막 주에 진행됩니다.",
             "event", "2026-03-05", 0),
        ]
    )

    conn.commit()
    print(f"  → 수강생 {len(students)}명, 강사 {len(teachers)}명, 패키지 3개, 슬롯 약 {slot_idx - 1000}개 생성")


def reset_db():
    """개발 DB 초기화 (모든 데이터 삭제 후 재생성)"""
    import os, sqlite3 as _sqlite3
    from app.database import SQLITE_PATH
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        print(f"🗑️ 개발 DB 삭제: {SQLITE_PATH}")
    conn = _sqlite3.connect(SQLITE_PATH)
    conn.row_factory = _sqlite3.Row
    init_sqlite_tables(conn)
    seed_if_empty(conn)
    conn.close()
    print("✅ 개발 DB 재생성 완료")


# CLI에서 직접 실행: python -m app.seed
if __name__ == "__main__":
    reset_db()
