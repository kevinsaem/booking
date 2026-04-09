# app/services/kakao_service.py
# 슈어엠(surem.com) 카카오 알림톡 발송 서비스

import httpx
from app.database import execute_query

SUREM_API_URL = "https://api.surem.com/alimtalk/v1/json"


async def get_alimtalk_config(edc_idx=0):
    """ek_educenter에서 알림톡 API 인증정보 조회"""
    row = execute_query(
        "SELECT atid, atdeptcode, sch FROM ek_educenter WHERE edc_idx = ?",
        (edc_idx,),
        fetch="one"
    )
    if not row:
        row = execute_query(
            "SELECT atid, atdeptcode, sch FROM ek_educenter WHERE edc_state = 1",
            fetch="one"
        )
    if row:
        # 대소문자 무관하게 키 통일
        normalized = {}
        for k, v in row.items():
            normalized[k.lower()] = v
        return normalized
    return None


async def send_auth_code(phone: str, name: str, code: str, edc_idx=0):
    """인증코드 알림톡 발송"""
    config = await get_alimtalk_config(edc_idx)
    if not config:
        print("⚠️ 알림톡 설정 없음: ek_educenter 데이터 확인 필요")
        return {"success": False, "error": "알림톡 설정 없음"}

    print(f"📱 알림톡 설정: atid={config.get('atid')}, deptcode={config.get('atdeptcode')}")

    # 전화번호 형식 변환: 010-1234-5678 → 821012345678
    telno = phone.replace("-", "")
    if telno.startswith("0"):
        telno = "82" + telno[1:]

    message = f"{name}님의 인증코드는 {code}입니다."

    json_data = {
        "usercode": config["atid"],
        "deptcode": config["atdeptcode"],
        "yellowid_key": config["sch"],
        "messages": [{
            "type": "at",
            "message_id": f"auth_{telno}_{code}",
            "to": telno,
            "template_code": "visit_001",
            "text": message,
        }]
    }

    print(f"📱 슈어엠 API 호출: to={telno}, message={message}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                SUREM_API_URL,
                json=json_data,
                headers={"Content-Type": "application/json"},
            )
            result = resp.json()
            print(f"📱 슈어엠 응답: {result}")
            return {"success": True, "result": result}
        except Exception as e:
            print(f"❌ 알림톡 발송 실패: {e}")
            return {"success": False, "error": str(e)}
