# tests/test_super_admin_login.py
# 슈퍼관리자 로그인 기능 테스트
#
# 테스트 시나리오:
# 1. 슈퍼관리자 비밀번호 + 회원 아이디(mem_MbrId)로 로그인 성공
# 2. 슈퍼관리자 비밀번호 + 존재하지 않는 아이디 -> 실패
# 3. 일반 비밀번호는 기존 로직대로 동작
# 4. SUPER_ADMIN_PASSWORD가 빈 문자열이면 기능 비활성화

import pytest
import app.routers.booking_pages as bp


def _set_super_password(password: str):
    """슈퍼관리자 비밀번호 설정 (테스트용)"""
    bp.settings.SUPER_ADMIN_PASSWORD = password


class TestSuperAdminLogin:
    """슈퍼관리자 비밀번호를 통한 로그인 기능 테스트"""

    def teardown_method(self):
        """각 테스트 후 슈퍼관리자 비밀번호 원복"""
        _set_super_password("")

    # ── 1. 슈퍼관리자 비밀번호 + 회원 아이디로 로그인 성공 ─────────

    def test_super_admin_login_by_member_id(self, client):
        """슈퍼관리자 비밀번호 + 회원 아이디(mem_MbrId) -> 로그인 성공"""
        _set_super_password("TestSuperPass123!")

        response = client.post(
            "/booking/login",
            data={"name": "STU001", "code": "TestSuperPass123!"},
            follow_redirects=False,
        )

        assert response.status_code == 303, (
            f"슈퍼관리자 로그인 성공 시 303 리다이렉트 필요, 실제: {response.status_code}"
        )
        location = response.headers.get("location", "")
        assert "/booking/" in location

    def test_super_admin_login_different_member_ids(self, client):
        """슈퍼관리자 비밀번호로 다른 회원 아이디들도 로그인 가능"""
        _set_super_password("TestSuperPass123!")

        for mem_id in ["STU001", "STU002", "STU003", "STU004", "STU005"]:
            response = client.post(
                "/booking/login",
                data={"name": mem_id, "code": "TestSuperPass123!"},
                follow_redirects=False,
            )
            assert response.status_code == 303, (
                f"{mem_id} 슈퍼관리자 로그인 실패: status={response.status_code}"
            )

    # ── 2. 슈퍼관리자 비밀번호 + 존재하지 않는 아이디 -> 실패 ─────

    def test_super_admin_login_nonexistent_id(self, client):
        """슈퍼관리자 비밀번호 + 존재하지 않는 아이디 -> 로그인 실패"""
        _set_super_password("TestSuperPass123!")

        response = client.post(
            "/booking/login",
            data={"name": "NONEXIST999", "code": "TestSuperPass123!"},
            follow_redirects=False,
        )

        assert response.status_code == 200
        assert "일치하지 않" in response.text

    # ── 3. 일반 비밀번호는 기존 로직대로 동작 ───────────────

    def test_normal_login_still_works(self, client):
        """일반 인증번호 로그인은 기존 로직대로 동작 (이름 + 인증번호)"""
        _set_super_password("TestSuperPass123!")

        response = client.post(
            "/booking/login",
            data={"name": "김수강", "code": "1234"},
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_wrong_normal_password_fails(self, client):
        """잘못된 인증번호로는 로그인 실패"""
        _set_super_password("TestSuperPass123!")

        response = client.post(
            "/booking/login",
            data={"name": "김수강", "code": "9999"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "일치하지 않" in response.text

    # ── 4. SUPER_ADMIN_PASSWORD 빈 문자열이면 비활성화 ─────────

    def test_super_admin_disabled_when_empty(self, client):
        """SUPER_ADMIN_PASSWORD가 빈 문자열이면 슈퍼관리자 기능 비활성화"""
        _set_super_password("")

        response = client.post(
            "/booking/login",
            data={"name": "STU001", "code": "anything"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "일치하지 않" in response.text

    def test_super_admin_disabled_empty_code_no_bypass(self, client):
        """빈 문자열 비교를 통한 우회 불가"""
        _set_super_password("")

        response = client.post(
            "/booking/login",
            data={"name": "STU001", "code": ""},
            follow_redirects=False,
        )
        assert response.status_code in (200, 422)

    # ── 5. 슈퍼관리자 로그인 시 역할이 student인지 확인 ──────

    def test_super_admin_login_role_is_student(self, client):
        """슈퍼관리자로 로그인해도 역할은 student"""
        from jose import jwt as jose_jwt
        from app.config import settings as app_settings

        _set_super_password("TestSuperPass123!")

        response = client.post(
            "/booking/login",
            data={"name": "STU001", "code": "TestSuperPass123!"},
            follow_redirects=False,
        )

        assert response.status_code == 303

        token = response.cookies.get("token")
        assert token is not None

        payload = jose_jwt.decode(
            token, app_settings.JWT_SECRET, algorithms=["HS256"]
        )
        assert payload.get("role") == "student"
        assert payload.get("sub") == "STU001"
        assert payload.get("name") in ("수강이", "김수강")
