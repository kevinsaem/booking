# app/routers/site_pages.py
# 홈페이지 라우터 (kevinsaem_2026에서 통합)
# 라우트: /, /youth, /adult, /corporate, /autobiography, /privacy, /refund, /tuition/*

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["site"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/index.html")


@router.get("/youth", response_class=HTMLResponse)
async def youth(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/youth.html")


@router.get("/adult", response_class=HTMLResponse)
async def adult(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/adult.html")


@router.get("/autobiography", response_class=HTMLResponse)
async def autobiography(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/autobiography.html")


@router.get("/corporate", response_class=HTMLResponse)
async def corporate(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/corporate.html")


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/privacy.html")


@router.get("/refund", response_class=HTMLResponse)
async def refund(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/refund.html")


@router.get("/tuition/youth", response_class=HTMLResponse)
async def tuition_youth(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/tuition-youth.html")


@router.get("/tuition/adult", response_class=HTMLResponse)
async def tuition_adult(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/tuition-adult.html")


@router.get("/tuition/corporate", response_class=HTMLResponse)
async def tuition_corporate(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/tuition-corporate.html")


@router.get("/tuition/autobiography", response_class=HTMLResponse)
async def tuition_autobiography(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/tuition-autobiography.html")


@router.get("/corporate-survey", response_class=HTMLResponse)
async def corporate_survey(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "site/corporate-survey.html")
