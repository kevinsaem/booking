# app/services/booking_service.py
# 예약 서비스: 예약 생성/취소, 잔여횟수 계산, 내 예약 조회

from datetime import datetime
from app.database import execute_query, get_db

DAYS_KO = ["일", "월", "화", "수", "목", "금", "토"]


def get_remaining(settle_code: int) -> int:
    """잔여 수업 횟수 계산
    
    ek_Package.class_cnt - ek_Sch_Detail_Room_mem(status=1) 건수
    """
    if not settle_code:
        return 0

    row = execute_query(
        "SELECT P.class_cnt - COUNT(R.idx) AS remaining "
        "FROM ek_Settlement S "
        "JOIN ek_Package P ON S.settle_package_code = P.package_code "
        "LEFT JOIN ek_Sch_Detail_Room_mem R "
        "  ON R.settle_code = S.settle_code AND R.status = 1 "
        "WHERE S.settle_code = ? AND S.settle_state = 1 "
        "GROUP BY P.class_cnt",
        (settle_code,),
        fetch="one"
    )
    return max(row["remaining"], 0) if row else 0


def create_booking(room_idx: int, mem_id: str, settle_code: int, dates: list) -> dict:
    """예약 생성 (1회 또는 반복)
    
    트랜잭션으로 전체 성공/실패 처리
    잔여횟수 재확인 (TOCTOU 방지)
    """
    remaining = get_remaining(settle_code)
    if remaining < len(dates):
        return {"success": False, "message": "잔여 수업 횟수가 부족합니다."}

    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # 슬롯 시간 정보 조회
            cursor.execute(
                "SELECT sch_detail_Stime, sch_detail_Etime "
                "FROM ek_Sch_Detail_Room WHERE sch_room_idx = ?",
                (room_idx,)
            )
            slot = cursor.fetchone()
            if not slot:
                return {"success": False, "message": "슬롯을 찾을 수 없습니다."}

            s_time_str = slot[0].strftime("%H:%M") if hasattr(slot[0], "strftime") else str(slot[0])
            e_time_str = slot[1].strftime("%H:%M") if hasattr(slot[1], "strftime") else str(slot[1])

            for date_str in dates:
                l_s = f"{date_str} {s_time_str}"
                l_f = f"{date_str} {e_time_str}"

                # 중복 예약 체크
                cursor.execute(
                    "SELECT COUNT(*) FROM ek_Sch_Detail_Room_mem "
                    "WHERE sch_room_idx = ? AND l_s_date = ? AND status = 1",
                    (room_idx, l_s)
                )
                if cursor.fetchone()[0] > 0:
                    raise ValueError(f"이미 예약된 시간입니다: {date_str}")

                # INSERT
                cursor.execute(
                    "INSERT INTO ek_Sch_Detail_Room_mem "
                    "(sch_room_idx, mem_mbrid, settle_code, "
                    " l_s_date, l_f_date, status, w_date) "
                    "VALUES (?, ?, ?, ?, ?, 1, GETDATE())",
                    (room_idx, mem_id, settle_code, l_s, l_f)
                )

            # 마지막 수업일로 mem_edate 갱신
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
    """예약 취소 (status → 0)
    
    24시간 전 체크는 라우터에서 처리
    취소 시 잔여횟수 자동 복원 (status=0이면 COUNT에 미포함)
    """
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
    """내 예약 목록 조회"""
    sql = (
        "SELECT R.idx, R.sch_room_idx, R.l_s_date, R.l_f_date, R.status, "
        "R.settle_code, "
        "ISNULL(B.mem_nickname, B.mem_MbrName) AS teacher_name "
        "FROM ek_Sch_Detail_Room_mem R "
        "JOIN ek_Sch_Detail_Room A ON R.sch_room_idx = A.sch_room_idx "
        "JOIN ek_Member B ON A.sch_teach_id = B.mem_MbrId "
        "WHERE R.mem_mbrid = ? "
    )
    params = [mem_id]

    if booking_idx:
        sql += "AND R.idx = ? "
        params.append(booking_idx)

    if upcoming:
        sql += "AND R.status = 1 AND R.l_s_date >= GETDATE() "

    sql += "ORDER BY R.l_s_date " + ("ASC" if upcoming else "DESC")

    rows = execute_query(sql, tuple(params), fetch="all")

    result = []
    now = datetime.now()
    for r in rows[:limit]:
        dt = r["l_s_date"]
        if isinstance(dt, str):
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")

        edt = r["l_f_date"]
        if isinstance(edt, str):
            edt = datetime.strptime(edt, "%Y-%m-%d %H:%M:%S")

        can_cancel = False
        dday_str = ""
        if r["status"] == 1:
            diff_sec = (dt - now).total_seconds()
            can_cancel = diff_sec > 86400  # 24시간
            diff_days = (dt.date() - now.date()).days
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
