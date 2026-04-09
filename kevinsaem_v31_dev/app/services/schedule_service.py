# app/services/schedule_service.py
# 스케줄 서비스: 가용 날짜/시간/강사 조회, 캘린더 셀, 반복 주차

from datetime import datetime, timedelta
from app.database import execute_query
import calendar as cal_mod


def get_available_dates(year: int, month: int) -> list:
    """해당 월의 예약 가능 날짜 목록 (문자열 리스트)
    
    ek_Sch_Detail_Room에서 status=1이고, 아직 예약 안 된 슬롯이 있는 날짜
    """
    rows = execute_query(
        "SELECT DISTINCT CONVERT(varchar(10), A.sch_detail_Stime, 23) AS avail_date "
        "FROM ek_Sch_Detail_Room A "
        "WHERE A.sch_room_status = 1 "
        "AND A.sch_detail_Stime >= GETDATE() "
        "AND YEAR(A.sch_detail_Stime) = ? "
        "AND MONTH(A.sch_detail_Stime) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ")",
        (year, month),
        fetch="all"
    )
    return [r["avail_date"] for r in rows]


def get_calendar_cells(year: int, month: int, available_dates: list) -> list:
    """캘린더 렌더링용 셀 리스트
    
    Returns:
        [{"empty": bool, "day": int, "available": bool, "date_str": str}, ...]
    """
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


def get_time_slots(date: str) -> list:
    """특정 날짜의 시간 슬롯 목록
    
    같은 시간대에 여러 강사가 있으면 teacher_count로 합산
    """
    rows = execute_query(
        "SELECT A.sch_room_idx, "
        "CONVERT(varchar(5), A.sch_detail_Stime, 108) AS s_time, "
        "CONVERT(varchar(5), A.sch_detail_Etime, 108) AS e_time, "
        "A.sch_teach_id "
        "FROM ek_Sch_Detail_Room A "
        "WHERE A.sch_room_status = 1 "
        "AND CONVERT(varchar(10), A.sch_detail_Stime, 23) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ") "
        "ORDER BY A.sch_detail_Stime",
        (date,),
        fetch="all"
    )

    time_groups = {}
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


def get_available_teachers(date: str, time: str, room_idx: int) -> list:
    """특정 날짜+시간의 가용 강사 목록"""
    s_time = time.split("~")[0]
    rows = execute_query(
        "SELECT B.mem_MbrId, B.mem_MbrName, B.mem_nickname, B.mem_MbrImg "
        "FROM ek_Sch_Detail_Room A "
        "JOIN ek_Member B ON A.sch_teach_id = B.mem_MbrId "
        "WHERE A.sch_room_status = 1 "
        "AND CONVERT(varchar(10), A.sch_detail_Stime, 23) = ? "
        "AND CONVERT(varchar(5), A.sch_detail_Stime, 108) = ? "
        "AND A.sch_room_idx NOT IN ("
        "  SELECT sch_room_idx FROM ek_Sch_Detail_Room_mem WHERE status = 1"
        ")",
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


def get_repeat_weeks(base_date: str, time: str, room_idx: int, teacher_id: str) -> list:
    """반복 예약 가능 주차 목록 (최대 12주)"""
    base = datetime.strptime(base_date, "%Y-%m-%d")
    DAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

    weeks = []
    for w in range(12):
        nd = base + timedelta(weeks=w)
        date_str = nd.strftime("%Y-%m-%d")
        day_name = DAYS_KO[nd.weekday()]

        available = True
        if w > 0:
            slot = execute_query(
                "SELECT COUNT(*) AS cnt FROM ek_Sch_Detail_Room A "
                "WHERE A.sch_teach_id = ? AND A.sch_room_status = 1 "
                "AND CONVERT(varchar(10), A.sch_detail_Stime, 23) = ? "
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
