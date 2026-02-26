"""
FastAPI SaaS Application for AI Karaoke Studio.

Endpoints:
  Web Pages  : /, /login, /register, /dashboard, /pricing, /admin, /profile
  API Auth   : /api/auth/*
  API Jobs   : /api/jobs/*
  API Billing: /api/billing/*
  API Admin  : /api/admin/*
  API Keys   : /api/keys/*
  Static     : /files/* (local storage)
  Docs       : /api/docs
"""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import Session

from .config import settings, SUBSCRIPTION_PLANS
from .database import get_db, create_tables
from .models.user import User
from .auth import get_current_user
from .routers import auth, jobs, billing, admin, api_keys

logger = logging.getLogger(__name__)

# ─── App Initialization ───────────────────────────────────────────────────────

app = FastAPI(
    title="AI Karaoke Studio API",
    description="Professional karaoke video generation powered by AI",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [settings.APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Templates & Static Files ─────────────────────────────────────────────────

SAAS_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(SAAS_DIR / "templates"))
templates.env.globals["get_flashed_messages"] = lambda with_categories=False: []

# Serve uploaded/output files
storage_path = settings.STORAGE_LOCAL_PATH
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(storage_path)), name="files")

# Serve static assets (CSS/JS/images)
static_dir = SAAS_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ─── API Routers ──────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(billing.router)
app.include_router(admin.router)
app.include_router(api_keys.router)


# ─── Template Context Helper ──────────────────────────────────────────────────

async def get_template_context(
    request: Request,
    db: Session,
    active_page: str = "",
) -> dict:
    """Build common template context with optional authenticated user."""
    context = {
        "request": request,
        "active_page": active_page,
        "current_user": None,
        "app_name": settings.APP_NAME,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }

    # Try to get user from cookie/session token
    token = request.cookies.get("access_token")
    if token:
        try:
            from .auth import decode_token, get_user_by_id
            payload = decode_token(token)
            user = get_user_by_id(db, payload.get("sub"))
            if user and user.is_active:
                context["current_user"] = {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_admin": user.is_admin,
                    "plan": user.current_plan,
                }
        except Exception:
            pass

    return context


# ─── Web Page Routes ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db)
    ctx["enumerate"] = enumerate  # for template use
    return templates.TemplateResponse("index.html", ctx)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db)
    if ctx["current_user"]:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", ctx)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db)
    if ctx["current_user"]:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("register.html", ctx)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db, active_page="dashboard")
    return templates.TemplateResponse("dashboard.html", ctx)


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db, active_page="pricing")
    ctx["plans"] = [{"id": k, **v} for k, v in SUBSCRIPTION_PLANS.items()]
    ctx["enumerate"] = enumerate
    return templates.TemplateResponse("pricing.html", ctx)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db, active_page="admin")
    if not ctx["current_user"] or not ctx["current_user"]["is_admin"]:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin.html", ctx)


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db)
    return templates.TemplateResponse("forgot_password.html", ctx)


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = "", db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db)
    ctx["reset_token"] = token
    return templates.TemplateResponse("reset_password.html", ctx)


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db, active_page="profile")
    return templates.TemplateResponse("profile.html", ctx)


@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request, db: Session = Depends(get_db)):
    ctx = await get_template_context(request, db, active_page="billing")
    ctx["plans"] = [{"id": k, **v} for k, v in SUBSCRIPTION_PLANS.items()]
    return templates.TemplateResponse("billing_page.html", ctx)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    db_ok = True
    try:
        db.execute("SELECT 1")
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "unavailable",
        "version": "2.0.0",
    }


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize database and storage on startup."""
    logger.info("Starting AI Karaoke Studio SaaS...")
    create_tables()
    logger.info("Database tables created/verified")

    # Create default admin user if not exists
    from .database import SessionLocal
    from .auth import hash_password, get_user_by_email
    from .models.subscription import Subscription

    admin_email = os.getenv("ADMIN_EMAIL", "admin@aikaraoke.studio")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123!")

    db = SessionLocal()
    try:
        if not get_user_by_email(db, admin_email):
            admin_user = User(
                email=admin_email,
                username="admin",
                hashed_password=hash_password(admin_password),
                full_name="System Admin",
                is_active=True,
                is_verified=True,
                is_admin=True,
            )
            db.add(admin_user)
            db.flush()

            sub = Subscription(
                user_id=admin_user.id,
                plan="enterprise",
                status="active",
            )
            db.add(sub)
            db.commit()
            logger.info(f"Created admin user: {admin_email}")
    finally:
        db.close()

    logger.info(f"AI Karaoke Studio SaaS started at {settings.APP_URL}")
