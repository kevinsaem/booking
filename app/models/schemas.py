# app/models/schemas.py
# Pydantic 스키마: API 입력/출력 검증

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, List


# ===== 인증 =====
class LoginRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="수강생 이름")
    code: str = Field(..., pattern=r"^\d{4}$", description="4자리 인증번호")


class LoginResponse(BaseModel):
    mem_MbrId: str
    name: str
    nickname: Optional[str] = None
    settle_code: int
    remaining: int
    campus_name: str
    token: str


# ===== 예약 =====
class BookingCreateRequest(BaseModel):
    room_idx: int
    settle_code: int
    teacher_id: str
    dates: List[date] = Field(..., min_length=1, max_length=12)


class BookingCancelRequest(BaseModel):
    idx: int


# ===== 스케줄 =====
class TimeSlot(BaseModel):
    time: str
    room_idx: int
    teacher_count: int
    available: bool


class TeacherInfo(BaseModel):
    id: str
    name: str
    img: Optional[str] = None
    field: str
    tag: Optional[str] = None


# ===== 공통 응답 =====
class ApiResponse(BaseModel):
    result: str  # "success" | "fail"
    data: Optional[dict] = None
    message: Optional[str] = None
