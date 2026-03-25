# app/services/kakao_service.py
# 카카오 알림톡 발송 서비스 (httpx 비동기)

import httpx
from app.config import settings


class KakaoService:
    """카카오 알림톡 발송 서비스

    FastAPI BackgroundTasks에서 호출:
        bg.add_task(kakao_service.send_booking_confirm, phone, ...)
    """

    async def send_auth_code(self, phone: str, code: str):
        """인증번호 발송"""
        return await self._send(phone, "AUTH_CODE", {"인증번호": code})

    async def send_booking_confirm(
        self, phone: str, name: str, teacher: str,
        date: str, time: str, campus: str, remaining: int
    ):
        """예약 확인 알림"""
        return await self._send(phone, "BOOKING_CONFIRM", {
            "수강생명": name, "강사명": teacher,
            "날짜": date, "시간": time,
            "캠퍼스명": campus, "잔여횟수": str(remaining),
        })

    async def send_booking_cancel(
        self, phone: str, name: str, teacher: str,
        date: str, time: str, remaining: int
    ):
        """예약 취소 알림"""
        return await self._send(phone, "BOOKING_CANCEL", {
            "수강생명": name, "강사명": teacher,
            "날짜": date, "시간": time,
            "잔여횟수": str(remaining),
        })

    async def _send(self, phone: str, template_code: str, variables: dict):
        """알림톡 API 호출"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    "https://kakao-alimtalk-api-url/send",  # 실제 URL로 교체
                    json={
                        "senderKey": settings.KAKAO_SENDER_KEY,
                        "templateCode": template_code,
                        "recipientList": [{
                            "recipientNo": phone,
                            "templateParameter": variables,
                        }],
                    },
                    headers={
                        "Authorization": f"Bearer {settings.KAKAO_API_KEY}",
                    },
                )
                return resp.json()
            except Exception as e:
                print(f"[알림톡 실패] {template_code}: {e}")
                return {"success": False, "error": str(e)}


kakao_service = KakaoService()
