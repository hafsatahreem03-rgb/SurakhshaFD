"""SurakshaFD API - hackathon demonstration prototype (not an official AICTE service)."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import SessionLocal
from .init_db import create_all
from .request_log import RequestLogMiddleware, setup_logging
from .routers import admin, auth, clearances, demo, fdrs, misc, reports
from .services.alerts import run_alerts

log = logging.getLogger("surakshafd")


async def _alert_loop():
    while True:
        try:
            with SessionLocal() as db:
                run_alerts(db)
        except Exception:  # never crash the server because of the background job
            log.exception("Alert job failed")
        await asyncio.sleep(settings.alert_interval_minutes * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    create_all()
    task = asyncio.create_task(_alert_loop()) if settings.alert_interval_minutes > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(
    title="SurakshaFD API",
    description="Smart FDR & Security Deposit Management Portal - SIH 2026 demonstration prototype by Team Lynxcode. "
                "Bank verification is SIMULATED. All data is fictional.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.add_middleware(RequestLogMiddleware)
for r in (auth.router, fdrs.router, clearances.router, reports.router, admin.router, misc.router, demo.router):
    app.include_router(r)


@app.get("/")
def root():
    return {"app": "SurakshaFD API", "docs": "/docs", "health": "/api/health",
            "notice": "Hackathon demonstration prototype - fictional data, simulated bank verification."}
