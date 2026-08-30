"""FastAPI app. Csak `127.0.0.1`-en fusson -- lasd webui/api README a WEBUI-TERV.md-ben.

Inditas: `./leadgen.sh ui` (vagy fejlesztes kozben kulon:
`.venv/bin/python -m uvicorn webui.api.main:app --host 127.0.0.1 --port 8000 --reload`).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import VERSION

app = FastAPI(title="leadgen webui", version=VERSION)

# A Next.js dev-szerver mas porton fut (3000), ezert kell CORS -- de csak
# localhosthoz, sehova mashova (Invariansok #5: csak localhost).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routers import (alerts, companies, costs, health, logs, meta,  # noqa: E402
                       replies, report, schedule)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(report.router)
app.include_router(companies.router)
app.include_router(replies.router)
app.include_router(alerts.router)
app.include_router(costs.router)
app.include_router(schedule.router)
app.include_router(logs.router)
