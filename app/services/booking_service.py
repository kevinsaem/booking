# app/services/booking_service.py
# 예약 서비스: 예약 생성/취소, 잔여횟수 계산, 내 예약 조회
# 주의: DB에 UTC로 저장됨 → 조회 시 +9시간 (한국 시간) 적용

from datetime import datetime, timedelta
from app.database import execute_query, get_db

DAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
KST_OFFSET = timedelta(hours=9)


def _get_settle_info(settle_code: int) -> dict | None:
    """수강권 + 패키지 정보 조회"""
    if not settle_code:
        return None
    return execute_query(
        "SELECT S.settle_code, S.settle_sdate, S.settle_edate, "
        "P.package_code, P.package_name, P.week_tcnt "
        "FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "WHERE S.settle_code = ? AND S.settle_state = 1",
        (settle_code,),
        fetch="one"
    )


def is_monthly_plan(settle_code: int) -> bool:
    """월수강권 여부 (패키지명에 '월수강권' 포함)"""
    info = _get_settle_info(settle_code)
    if not info:
        return False
    return "월수강권" in (info.get("package_name") or "")


def get_remaining(settle_code: int) -> int:
    """잔여 수업 횟수 계산

    - 월수강권: 기간 내이면 999 (무제한), 기간 외면 0
    - 횟수제: week_tcnt - 사용한 예약 건수
    """
    info = _get_settle_info(settle_code)
    if not info:
        return 0

    # 월수강권: 기간 체크
    if "월수강권" in (info.get("package_name") or ""):
        from datetime import datetime
        now_kst = datetime.utcnow() + KST_OFFSET
        try:
            sdate = datetime.strptime(info["settle_sdate"][:10], "%Y-%m-%d")
            edate = datetime.strptime(info["settle_edate"][:10], "%Y-%m-%d")
            if sdate.date() <= now_kst.date() <= edate.date():
                return 999  # 무제한
            else:
                return 0  # 기간 만료
        except (ValueError, TypeError):
            return 0

    # 횟수제: week_tcnt - 사용 건수
    row = execute_query(
        "SELECT P.week_tcnt - COUNT(R.idx) AS remaining "
        "FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "LEFT JOIN ek_Sch_Detail_Room_mem R "
        "  ON R.settle_code = S.settle_code AND R.status = 1 "
        "WHERE S.settle_code = ? AND S.settle_state = 1 "
        "GROUP BY P.week_tcnt",
        (settle_code,),
        fetch="one"
    )
    return max(row["remaining"], 0) if row else 0


def get_total_classes(settle_code: int) -> int:
    """총 제공 수업 횟수

    - 월수강권: 0 반환 (횟수 개념 없음, 화면에서 별도 처리)
    - 횟수제: week_tcnt
    """
    info = _get_settle_info(settle_code)
    if not info:
        return 0

    if "월수강권" in (info.get("package_name") or ""):
        return 0  # 월수강권은 횟수 개념 없음

    return info.get("week_tcnt") or 0


def get_settle_period(settle_code: int) -> dict | None:
    """수강권 기간 정보 (월수강권용)"""
    info = _get_settle_info(settle_code)
    if not info:
        return None
    return {
        "package_name": info.get("package_name", ""),
        "sdate": (info.get("settle_sdate") or "")[:10],
        "edate": (info.get("settle_edate") or "")[:10],
        "is_monthly": "월수강권" in (info.get("package_name") or ""),
    }


def create_booking(room_idx: int, mem_id: str, settle_code: int, dates: list) -> dict:
    """예약 생성 (1회 또는 반복)"""
    remaining = get_remaining(settle_code)
    if remaining < len(dates):
        return {"success": False, "message": "잔여 수업 횟수가 부족합니다."}

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # 슬롯 시간 정보 조회 (UTC) → KST 변환
            cursor.execute(
                "SELECT datetime(sch_detail_Stime, '+9 hours') AS kst_stime, "
                "datetime(sch_detail_Etime, '+9 hours') AS kst_etime "
                "FROM ek_Sch_Detail_Room WHERE sch_room_idx = ?",
                (room_idx,)
            )
            slot = cursor.fetchone()
            if not slot:
                return {"success": False, "message": "슬롯을 찾을 수 없습니다."}

            if hasattr(slot, "keys"):
                kst_stime = slot["kst_stime"]
                kst_etime = slot["kst_etime"]
            else:
                kst_stime = slot[0]
                kst_etime = slot[1]

            # KST 시간에서 시:분 추출
            s_time_str = str(kst_stime).split(" ")[1][:5] if " " in str(kst_stime) else str(kst_stime)[:5]
            e_time_str = str(kst_etime).split(" ")[1][:5] if " " in str(kst_etime) else str(kst_etime)[:5]

            for date_str in dates:
                # KST 시간으로 l_s_date, l_f_date 생성 → UTC로 변환해서 저장
                kst_start = datetime.strptime(f"{date_str} {s_time_str}:00", "%Y-%m-%d %H:%M:%S")
                kst_end = datetime.strptime(f"{date_str} {e_time_str}:00", "%Y-%m-%d %H:%M:%S")
                utc_start = kst_start - KST_OFFSET
                utc_end = kst_end - KST_OFFSET
                l_s = utc_start.strftime("%Y-%m-%d %H:%M:%S")
                l_f = utc_end.strftime("%Y-%m-%d %H:%M:%S")

                # 중복 예약 체크
                cursor.execute(
                    "SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem "
                    "WHERE sch_room_idx = ? AND l_s_date = ? AND status = 1",
                    (room_idx, l_s)
                )
                count_row = cursor.fetchone()
                count_val = count_row[0] if isinstance(count_row, (tuple, list)) else list(count_row)[0]
                if count_val > 0:
                    raise ValueError(f"이미 예약된 시간입니다: {date_str}")

                cursor.execute(
                    "INSERT INTO ek_Sch_Detail_Room_mem "
                    "(sch_room_idx, mem_mbrid, settle_code, "
                    " l_s_date, l_f_date, status, w_date) "
                    "VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
                    (room_idx, mem_id, settle_code, l_s, l_f)
                )

            last_date = sorted(dates)[-1]
            cursor.execute(
                "UPDATE ek_Member SET mem_edate = ? WHERE mem_mbrid = ?",
                (last_date, mem_id)
            )

            conn.commit()
            return {"success": True, "count": len(dates)}

        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def cancel_booking(idx: int, mem_id: str) -> bool:
    """예약 취소 (status -> 0)"""
    affected = execute_query(
        "UPDATE ek_Sch_Detail_Room_mem "
        "SET status = 0 "
        "WHERE idx = ? AND mem_mbrid = ? AND status = 1",
        (idx, mem_id),
        fetch="none"
    )
    return affected > 0


def get_my_bookings(
    mem_id: str,
    limit: int = 50,
    upcoming: bool = False,
    booking_idx: int = None
) -> list:
    """내 예약 목록 조회 (UTC → KST 변환)"""
    sql = (
        "SELECT R.idx, R.sch_room_idx, "
        "datetime(R.l_s_date, '+9 hours') AS kst_s_date, "
        "datetime(R.l_f_date, '+9 hours') AS kst_f_date, "
        "R.status, R.settle_code, "
        "COALESCE(B.mem_nickname, B.mem_MbrName) AS teacher_name "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "JOIN ek_Member B ON A.sch_teach_id = B.mem_MbrId "
        "WHERE R.mem_mbrid = ? "
    )
    params: list = [mem_id]

    if booking_idx:
        sql += "AND R.idx = ? "
        params.append(booking_idx)

    if upcoming:
        sql += "AND R.status = 1 AND datetime(R.l_s_date, '+9 hours') >= datetime('now', '+9 hours') "

    sql += "ORDER BY R.l_s_date " + ("ASC" if upcoming else "DESC")

    rows = execute_query(sql, tuple(params), fetch="all")

    result = []
    now_kst = datetime.utcnow() + KST_OFFSET
    for r in rows[:limit]:
        dt = r["kst_s_date"]
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

        edt = r["kst_f_date"]
        if isinstance(edt, str):
            edt = datetime.strptime(edt, "%Y-%m-%d %H:%M:%S")

        can_cancel = False
        dday_str = ""
        if r["status"] == 1:
            diff_sec = (dt - now_kst).total_seconds()
            can_cancel = diff_sec > 43200  # 12시간
            diff_days = (dt.date() - now_kst.date()).days
            if diff_days == 0:
                dday_str = "D-Day"
            elif diff_days > 0:
                dday_str = f"D-{diff_days}"

        result.append({
            "idx": r["idx"],
            "date": dt,
            "date_label": f"{dt.year}.{dt.month}.{dt.day} ({DAYS_KO[dt.weekday()]})",
            "month": dt.month,
            "day": dt.day,
            "day_name": DAYS_KO[dt.weekday()],
            "time": f"{dt.strftime('%H:%M')}~{edt.strftime('%H:%M')}",
            "teacher_name": r.get("teacher_name", ""),
            "status": r["status"],
            "can_cancel": can_cancel,
            "dday": dday_str,
        })

    return result
