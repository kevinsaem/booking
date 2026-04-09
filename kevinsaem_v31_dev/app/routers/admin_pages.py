# app/routers/admin_pages.py
# 관리자 웹 라우터 (HTMX + Jinja2)
# URL 패턴: /admin/*
# TODO: 관리자 인증 미들웨어, 슬롯 CRUD, 예약 관리

from fastapi import APIRouter
router = APIRouter(prefix="/admin", tags=["관리자 웹"])

# TODO: 대시보드, 슬롯 관리, 예약 현황 페이지
