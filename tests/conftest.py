# tests/conftest.py
# pytest 공통 설정 - 개발 모드(SQLite) 테스트 환경 구성

import sys
import os

# 프로젝트 루트를 path에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def reset_dev_db():
    """테스트 세션 시작 전 개발 DB 초기화"""
    os.environ["DB_MODE"] = "development"
    from app.seed import reset_db
    reset_db()


@pytest.fixture(scope="session")
def app():
    """FastAPI 앱 인스턴스"""
    from main import app as _app
    return _app


@pytest.fixture(scope="session")
def client(app):
    """TestClient (세션 스코프 - 재사용)"""
    return TestClient(app, raise_server_exceptions=False)
