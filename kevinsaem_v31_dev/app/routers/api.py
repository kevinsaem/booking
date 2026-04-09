# app/routers/api.py
# JSON API 라우터 (시스템용, 웹훅)
# URL 패턴: /api/v1/*

from fastapi import APIRouter
router = APIRouter(prefix="/api/v1", tags=["API"])

# TODO: 카카오 웹훅, 외부 연동 API
