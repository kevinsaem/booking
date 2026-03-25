# app/services/schedule_service.py
# 스케줄 서비스: 가용 날짜/시간/강사 조회, 캘린더 셀, 반복 주차
# 주의: DB에 UTC로 저장됨 → 조회 시 +9시간 (한국 시간) 적용
# wb_idx=357 (성인1:1) → 멘토(mem_MbrType='4')만 필터

from datetime import datetime, timedelta
from app.database import execute_query
import calendar as cal_mod

# UTC → KST 변환 SQL (SQLite)
KST_STIME = "datetime(A.sch_detail_Stime, '+9 hours')"
KST_ETIME = "datetime(A.sch_detail_Etime, '+9 hours')"
KST_NOW = "datetime('now', '+9 hours')"

# 성인 1:1 과정 wb_idx
ADULT_1ON1_WB_IDX = 357
MENTOR_1ON1_TYPE = '4'   # 성인 1:1 멘토
MENTOR_VIRTUAL_TYPE = '5'  # 가상교사


def _get_wb_idx(settle_code: int) -> int:
    """수강생의 wb_idx 조회"""
    if not settle_code:
        return 0
    row = execute_query(
        "SELECT wb_idx FROM ek_Settlement WHERE settle_code = ? AND settle_state = 1",
        (settle_code,),
        fetch="one"
    )
    return row["wb_idx"] if row else 0


def _teacher_filter(wb_idx: int) -> str:
    """wb_idx에 따른 멘토 타입 필터 SQL"""
    if wb_idx == ADULT_1ON1_WB_IDX:
        # 성인 1:1 → 타입4만
        return f"AND A.sch_teach_id IN (SELECT mem_MbrId FROM ek_Member WHERE mem_MbrType = '{MENTOR_1ON1_TYPE}') "
    else:
        # 일반 과정 → 타입5(가상교사)만
        return f"AND A.sch_teach_id IN (SELECT mem_MbrId FROM ek_Member WHERE mem_MbrType = '{MENTOR_VIRTUAL_TYPE}') "


def get_available_dates(year: int, month: int, settle_code: int = 0) -> list:
    """해당 월의 예약 가능 날짜 목록 (한국 시간 기준)"""
    wb_idx = _get_wb_idx(settle_code)
    mentor_sql = _teacher_filter(wb_idx)

    rows = execute_query(
        f"SELECT DISTINCT strftime('%Y-%m-%d', {KST_STIME}) AS avail_date "
        "FROM ek_Sch_Detail_Room A "
        "WHERE A.sch_room_status = 1 "
        f"AND {KST_STIME} >= {KST_NOW} "
        f"AND cast(strftime('%Y', {KST_STIME}) as integer) = ? "
        f"AND cast(strftime('%m', {KST_STIME}) as integer) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ") "
        + mentor_sql,
        (year, month),
        fetch="all"
    )
    return [r["avail_date"] for r in rows]


def get_calendar_cells(year: int, month: int, available_dates: list) -> list:
    """캘린더 렌더링용 셀 리스트"""
    first_weekday = cal_mod.monthrange(year, month)[0]  # 0=Mon
    first_weekday = (first_weekday + 1) % 7  # 0=Sun 변환
    last_day = cal_mod.monthrange(year, month)[1]

    cells = []
    for _ in range(first_weekday):
        cells.append({"empty": True, "day": 0, "available": False, "date_str": ""})

    for d in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{d:02d}"
        cells.append({
            "empty": False,
            "day": d,
            "available": date_str in available_dates,
            "date_str": date_str,
        })

    return cells


def get_time_slots(date: str, settle_code: int = 0) -> list:
    """특정 날짜의 시간 슬롯 목록 (한국 시간 기준)"""
    wb_idx = _get_wb_idx(settle_code)
    mentor_sql = _teacher_filter(wb_idx)

    rows = execute_query(
        "SELECT A.sch_room_idx, "
        f"strftime('%H:%M', {KST_STIME}) AS s_time, "
        f"strftime('%H:%M', {KST_ETIME}) AS e_time, "
        "A.sch_teach_id "
        "FROM ek_Sch_Detail_Room A "
        "WHERE A.sch_room_status = 1 "
        f"AND strftime('%Y-%m-%d', {KST_STIME}) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ") "
        + mentor_sql
        + f"ORDER BY {KST_STIME}",
        (date,),
        fetch="all"
    )

    time_groups: dict = {}
    for r in rows:
        time_key = f"{r['s_time']}~{r['e_time']}"
        if time_key not in time_groups:
            time_groups[time_key] = {
                "time": time_key,
                "room_idx": r["sch_room_idx"],
                "teacher_count": 0,
                "available": True,
            }
        time_groups[time_key]["teacher_count"] += 1

    return list(time_groups.values())


def get_available_teachers(date: str, time: str, room_idx: int, settle_code: int = 0) -> list:
    """특정 날짜+시간의 가용 멘토 목록 (한국 시간 기준)"""
    s_time = time.split("~")[0]
    wb_idx = _get_wb_idx(settle_code)
    mentor_sql = _teacher_filter(wb_idx)

    rows = execute_query(
        "SELECT B.mem_MbrId, B.mem_MbrName, B.mem_nickname, B.mem_MbrImg "
        "FROM ek_Sch_Detail_Room A "
        "JOIN ek_Member B ON A.sch_teach_id = B.mem_MbrId "
        "WHERE A.sch_room_status = 1 "
        f"AND strftime('%Y-%m-%d', {KST_STIME}) = ? "
        f"AND strftime('%H:%M', {KST_STIME}) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ") "
        + mentor_sql,
        (date, s_time),
        fetch="all"
    )

    return [{
        "id": r["mem_MbrId"],
        "name": r.get("mem_nickname") or r["mem_MbrName"],
        "img": r.get("mem_MbrImg"),
        "field": "AI활용 과정",
        "tag": "",
    } for r in rows]


def get_repeat_weeks(base_date: str, time: str, room_idx: int, teacher_id: str, remaining: int = 12) -> list:
    """반복 예약 가능 주차 목록 (남은 수업수만큼, 한국 시간 기준)

    remaining=999(월수강권)이면 최대 12주까지 표시
    """
    base = datetime.strptime(base_date, "%Y-%m-%d")
    DAYS_KO_LOCAL = ["월", "화", "수", "목", "금", "토", "일"]

    max_weeks = min(remaining, 12)  # 최대 12주, 남은 수업수 이내

    weeks = []
    for w in range(max_weeks):
        nd = base + timedelta(weeks=w)
        date_str = nd.strftime("%Y-%m-%d")
        day_name = DAYS_KO_LOCAL[nd.weekday()]

        available = True
        if w > 0:
            slot = execute_query(
                "SELECT COUNT(*) AS cnt FROM ek_Sch_Detail_Room A "
                "WHERE A.sch_teach_id = ? AND A.sch_room_status = 1 "
                f"AND strftime('%Y-%m-%d', {KST_STIME}) = ? "
                "AND A.sch_room_idx NOT IN ("
                "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
                ")",
                (teacher_id, date_str),
                fetch="one"
            )
            available = slot and slot["cnt"] > 0

        weeks.append({
            "idx": w,
            "date": date_str,
            "label": f"{nd.month}/{nd.day} ({day_name}) {time}",
            "disabled": not available,
        })

    return weeks
