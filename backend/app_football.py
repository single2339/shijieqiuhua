"""Minimal FastAPI app for shijieqiuhua — no osint-network agent deps."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_dotenv = Path(__file__).resolve().parent.parent / ".env"
if _dotenv.exists():
    from dotenv import load_dotenv
    load_dotenv(_dotenv)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="ShijieQiuhua API", version="1.0.0", lifespan=lifespan)

_allowed = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in _allowed if o.strip()],
                   allow_methods=["*"], allow_headers=["*"])

# ── rate limiting (mirror of main.py middleware) ──
import time as _time
from fastapi import Request
from fastapi.responses import JSONResponse
_rate_store: dict[str, list[float]] = {}

def _client_ip(request: Request) -> str:
    # Behind nginx every request's client.host is 127.0.0.1, which would make
    # the limiter throttle ALL users as one. Trust the proxy's X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = _client_ip(request)
    now = _time.time()
    window = [t for t in _rate_store.get(ip, []) if now - t < 60]
    limit = 20 if request.method in ("POST", "PUT", "DELETE") else 120
    if len(window) >= limit:
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})
    window.append(now)
    _rate_store[ip] = window
    if len(_rate_store) > 4096:
        oldest = sorted(_rate_store, key=lambda k: min(_rate_store[k] or [0]))[:1024]
        for k in oldest: del _rate_store[k]
    return await call_next(request)

from backend.auth.routes import router as auth_router
from backend.auth.admin_routes import router as admin_router
from backend.football_osint.routes import router as football_osint_router
from backend.billing.routes import router as billing_router

app.include_router(auth_router, prefix="/api/auth")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(football_osint_router)
app.include_router(billing_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "shijieqiuhua"}
