# app/seed.py
# SQLite 테이블 생성 + Mock 데이터 시딩
#
# 실서버 MS-SQL의 테이블 구조를 SQLite로 재현합니다.
# 프로토타입 HTML(케빈샘_완전동작_프로토타입_v3.html)의 모든 데이터를 포함합니다.

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

    # === dev_messages: 메시지 (레거시, 호환용) ===
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

    # === ek_message: 1:1 메시지 시스템 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_message (
            msg_idx INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            parent_msg_idx INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)

    # === ek_message_token: 멘토 답변 토큰 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS ek_message_token (
            token_idx INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            msg_idx INTEGER NOT NULL,
            mentor_id TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # === dev_notices: 공지사항 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS dev_notices (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            summary TEXT,
            content TEXT,
            type TEXT DEFAULT 'notice',
            created_at TEXT NOT NULL,
            is_new INTEGER DEFAULT 0
        )
    """)

    # === dev_lesson_history: 수업 이력 (학습 대시보드용) ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS dev_lesson_history (
            lesson_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mem_id TEXT NOT NULL,
            teacher_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            lesson_date TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            FOREIGN KEY (mem_id) REFERENCES ek_Member(mem_MbrId),
            FOREIGN KEY (teacher_id) REFERENCES ek_Member(mem_MbrId)
        )
    """)

    # === dev_class_memos: 수업 메모 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS dev_class_memos (
            memo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            lesson_date TEXT NOT NULL,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # === kakao_members: 카카오 로그인 회원 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS kakao_members (
            kakao_id TEXT PRIMARY KEY,
            mem_id TEXT NOT NULL UNIQUE,
            nickname TEXT,
            profile_img TEXT,
            email TEXT,
            phone TEXT,
            role TEXT DEFAULT 'student',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # === agreement_templates: 계약서 템플릿 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS agreement_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            course_type TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # === agreement_signatures: 전자서명 기록 ===
    c.execute("""
        CREATE TABLE IF NOT EXISTS agreement_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mem_MbrId TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            signature_image TEXT NOT NULL,
            agreed_at TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            device_info TEXT,
            document_hash TEXT,
            is_valid INTEGER DEFAULT 1,
            FOREIGN KEY (mem_MbrId) REFERENCES ek_Member(mem_MbrId),
            FOREIGN KEY (template_id) REFERENCES agreement_templates(id)
        )
    """)

    conn.commit()


def seed_if_empty(conn):
    """테이블이 비어있으면 Mock 데이터 삽입"""
    c = conn.cursor()

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
    # 프로토타입 기준: 취미반 210,000원 / 진로반 290,000원 / 월정기 450,000원
    c.executemany(
        "INSERT INTO ek_Package (package_code, package_name, class_cnt, lec_time, month_cnt, price) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (101, "취미반 주2회", 8, 50, 1, 210000),
            (102, "진로반 주2회", 20, 50, 2, 290000),
            (103, "월정기 진로반", 40, 50, 1, 450000),
        ]
    )

    # ===== 3. 회원 (수강생 5명 + 강사 3명) =====
    # 프로토타입 테스트 계정과 동일
    students = [
        ("STU001", "김수강", "수강이", None, "01012345678", "2", None, "1234", 1),
        ("STU002", "이학생", "학생이", None, "01023456789", "2", None, "5678", 1),
        ("STU003", "박공부", "공부왕", None, "01034567890", "2", None, "9012", 1),
        ("STU004", "최열심", "열심이", None, "01045678901", "2", None, "3456", 2),
        ("STU005", "정성실", "성실이", None, "01056789012", "2", None, "7890", 1),
    ]
    # 강사 (mem_MbrType=4: 1:1 멘토)
    teachers = [
        ("TEA001", "김코딩", "김코딩", None, "01098765432", "4", None, "1111", 1),
        ("TEA002", "박데이터", "박데이터", None, "01087654321", "4", None, "2222", 1),
        ("TEA003", "이웹개발", "이웹개발", None, "01076543210", "4", None, "3333", 1),
    ]
    # 관리자
    admins = [
        ("ADM001", "관리자", "관리자", None, "01099999999", "admin", None, "0000", 1),
    ]
    c.executemany(
        "INSERT INTO ek_Member VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        students + teachers + admins
    )

    # ===== 4. 결제 (수강권) =====
    # 프로토타입 기준: 김수강=진로반20회(잔여7), 이학생=취미반8회, 박공부=월정기40회, 최열심=진로반20회, 정성실=취미반8회
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
    # 프로토타입 기준 시간대: 10:00, 11:00, 14:00, 16:00, 17:00
    time_patterns = [
        ("10:00", "10:50"),
        ("11:00", "11:50"),
        ("14:00", "14:50"),
        ("15:00", "15:50"),
        ("16:00", "16:50"),
        ("17:00", "17:50"),
    ]
    # 프로토타입 기준 강사 배치
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
                continue
            date_str = date.strftime("%Y-%m-%d")
            for s_time, e_time in time_patterns:
                for teacher_id in teacher_assignments.get(s_time, []):
                    slot_idx += 1
                    c.execute(
                        "INSERT INTO ek_Sch_Detail_Room (sch_room_idx, sch_teach_id, sch_detail_Stime, sch_detail_Etime, sch_room_status, edc_idx) VALUES (?, ?, ?, ?, 1, 1)",
                        (slot_idx, teacher_id, f"{date_str} {s_time}:00", f"{date_str} {e_time}:00")
                    )

    # ===== 6. 기존 예약 (김수강의 과거 수업 13회 → 잔여 7회) =====
    past_dates = [(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(1, 28, 2)]
    for i, pdate in enumerate(past_dates[:13]):
        teacher = "TEA001" if i % 2 == 0 else "TEA002"
        c.execute(
            "INSERT INTO ek_Sch_Detail_Room_mem (sch_room_idx, mem_mbrid, settle_code, l_s_date, l_f_date, status, w_date) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (1001 + i, "STU001", 10001, f"{pdate} 14:00:00", f"{pdate} 14:50:00", pdate)
        )

    # ===== 7. 메시지 (프로토타입 채팅 내용과 동일) =====
    c.executemany(
        "INSERT INTO dev_messages (sender_id, receiver_id, content, sent_at, is_read) VALUES (?, ?, ?, ?, ?)",
        [
            ("STU001", "TEA001", "선생님 다음 수업은 어떤 내용인가요?", f"{today} 14:30:00", 1),
            ("TEA001", "STU001", "다음 수업에서는 ChatGPT API를 활용한 프롬프트 엔지니어링을 다룰 예정입니다.", f"{today} 14:35:00", 0),
            ("STU001", "TEA001", "준비물이 있을까요?", f"{today} 14:36:00", 1),
            ("TEA001", "STU001", "OpenAI API 키만 준비해주시면 됩니다. 수업 전에 발급 방법도 안내드릴게요!", f"{today} 14:40:00", 0),
            ("TEA002", "STU001", "과제 확인했습니다. 잘 하셨어요!", f"{(now - timedelta(days=1)).strftime('%Y-%m-%d')} 10:15:00", 1),
        ]
    )

    # ===== 8. 공지사항 (프로토타입과 동일) =====
    c.executemany(
        "INSERT INTO dev_notices (title, summary, content, type, created_at, is_new) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("4월 AI활용 특강 안내",
             "ChatGPT, Claude 실전 활용법",
             "ChatGPT, Midjourney, Claude를 활용한 실전 AI 활용법을 배우는 특강이 4월에 진행됩니다. 수강생 여러분의 많은 관심 부탁드립니다.",
             "notice", "2026-03-20", 1),
            ("설 연휴 휴원 안내",
             "2/7~2/11 휴원",
             "2/7(금)~2/11(화) 설 연휴 기간 동안 휴원합니다. 수업은 2/12(수)부터 정상 진행됩니다.",
             "notice", "2026-03-15", 0),
            ("친구 추천 이벤트 - 1회 무료!",
             "추천인+피추천인 1회 무료",
             "성인반 친구를 추천하시면 추천인과 피추천인 모두 1회 무료 수업을 드립니다. 카카오톡으로 문의해주세요.",
             "event", "2026-03-10", 0),
            ("Python 기초 무료 특강",
             "3월 마지막 주 진행",
             "Python을 처음 접하시는 분들을 위한 무료 특강이 3월 마지막 주에 진행됩니다.",
             "event", "2026-03-05", 0),
        ]
    )

    # ===== 9. 수업 이력 (프로토타입 학습 대시보드와 동일) =====
    c.executemany(
        "INSERT INTO dev_lesson_history (mem_id, teacher_id, topic, lesson_date, status) VALUES (?, ?, ?, ?, ?)",
        [
            ("STU001", "TEA001", "ChatGPT API 활용", "2026-03-19", "completed"),
            ("STU001", "TEA002", "Python 데이터 분석", "2026-03-17", "completed"),
            ("STU001", "TEA001", "AI 이미지 생성", "2026-03-14", "completed"),
            ("STU001", "TEA002", "Pandas 기초", "2026-03-12", "completed"),
            ("STU001", "TEA001", "ChatGPT 프롬프트 작성법", "2026-03-10", "completed"),
        ]
    )

    # ===== 10. 카카오 회원 (관리자 + 강사 테스트 계정) =====
    c.execute(
        "INSERT OR IGNORE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
        ("admin_test", "ADM001", "관리자", "admin")
    )
    c.execute(
        "INSERT OR IGNORE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
        ("teacher_test_1", "TEA001", "김코딩", "teacher")
    )
    c.execute(
        "INSERT OR IGNORE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
        ("teacher_test_2", "TEA002", "박데이터", "teacher")
    )
    c.execute(
        "INSERT OR IGNORE INTO kakao_members (kakao_id, mem_id, nickname, role) VALUES (?, ?, ?, ?)",
        ("teacher_test_3", "TEA003", "이웹개발", "teacher")
    )

    # ===== 계약서 템플릿 시딩 =====
    import os
    agreement_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "자료실", "agreement_content.md")
    if os.path.exists(agreement_path):
        with open(agreement_path, "r", encoding="utf-8") as f:
            agreement_content = f.read()
        c.execute(
            "INSERT INTO agreement_templates (version, title, content, course_type, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            ("v1.0", "교육 서비스 이용 계약서", agreement_content, "1:1 성인 AI 활용 과정")
        )

    conn.commit()
    print(f"  → 수강생 {len(students)}명, 강사 {len(teachers)}명, 패키지 3개, 슬롯 약 {slot_idx - 1000}개 생성")


def reset_db():
    """개발 DB 초기화 (모든 데이터 삭제 후 재생성)"""
    import os
    import sqlite3 as _sqlite3
    from app.database import SQLITE_PATH
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)
        print(f"🗑️  개발 DB 삭제: {SQLITE_PATH}")
    conn = _sqlite3.connect(SQLITE_PATH)
    conn.row_factory = _sqlite3.Row
    init_sqlite_tables(conn)
    seed_if_empty(conn)
    conn.close()
    print("✅ 개발 DB 재생성 완료")


if __name__ == "__main__":
    reset_db()
