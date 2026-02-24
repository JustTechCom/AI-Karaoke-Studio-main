"""
Authentication router: register, login, logout, password reset, email verification.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.subscription import Subscription
from ..auth import (
    hash_password, verify_password, authenticate_user,
    create_access_token, create_refresh_token, decode_token,
    get_current_active_user, generate_verification_token, get_user_by_email,
)
from ..config import settings
from ..email_service import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

    @validator("username")
    def username_alphanumeric(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Kullanıcı adı yalnızca harf, rakam, _ ve - içerebilir")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Kullanıcı adı 3-50 karakter arasında olmalı")
        return v.lower()

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    username: str
    is_admin: bool
    plan: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @validator("new_password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalı")
        return v


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a new user account."""
    # Check if email already exists
    if db.query(User).filter(User.email == request.email).first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kullanımda")

    # Check if username already exists
    if db.query(User).filter(User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten kullanımda")

    # Create user
    verification_token = generate_verification_token()
    user = User(
        email=request.email,
        username=request.username,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        verification_token=verification_token,
        verification_token_expires=datetime.utcnow() + timedelta(hours=24),
        is_verified=False,
    )
    db.add(user)
    db.flush()  # Get user ID

    # Create free subscription
    subscription = Subscription(
        user_id=user.id,
        plan="free",
        status="active",
    )
    db.add(subscription)
    db.commit()
    db.refresh(user)

    # Send verification email in background
    background_tasks.add_task(
        send_verification_email,
        user.email,
        user.username,
        verification_token,
    )

    return {
        "message": "Hesap oluşturuldu. Lütfen e-postanızı doğrulayın.",
        "user_id": user.id,
    }


@router.post("/token", response_model=TokenResponse)
async def login_for_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login with username/password and get JWT tokens (OAuth2 compatible)."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Hatalı e-posta veya şifre",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Hesap deaktif edilmiş")

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
        plan=user.current_plan,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """Login with email/password."""
    user = authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Hatalı e-posta veya şifre")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Hesap deaktif edilmiş")

    user.last_login_at = datetime.utcnow()
    db.commit()

    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
        plan=user.current_plan,
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh JWT access token using refresh token."""
    payload = decode_token(request.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Geçersiz token türü")

    user_id = payload.get("sub")
    from ..auth import get_user_by_id
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")

    access_token = create_access_token({"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify email address with token."""
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Geçersiz doğrulama kodu")
    if user.verification_token_expires and datetime.utcnow() > user.verification_token_expires:
        raise HTTPException(status_code=400, detail="Doğrulama kodunun süresi dolmuş")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()

    return RedirectResponse(url="/?verified=true", status_code=302)


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Request password reset email."""
    user = get_user_by_email(db, request.email)
    if user:  # Don't reveal if email exists
        reset_token = generate_verification_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=2)
        db.commit()

        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            user.username,
            reset_token,
        )

    return {"message": "Şifre sıfırlama e-postası gönderildi (eğer hesap mevcutsa)"}


@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Reset password using token."""
    user = db.query(User).filter(User.reset_token == request.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Geçersiz sıfırlama kodu")
    if user.reset_token_expires and datetime.utcnow() > user.reset_token_expires:
        raise HTTPException(status_code=400, detail="Sıfırlama kodunun süresi dolmuş")

    user.hashed_password = hash_password(request.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Şifre başarıyla güncellendi"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Change password for authenticated user."""
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")

    current_user.hashed_password = hash_password(request.new_password)
    db.commit()

    return {"message": "Şifre başarıyla değiştirildi"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_verified": current_user.is_verified,
        "is_admin": current_user.is_admin,
        "plan": current_user.current_plan,
        "created_at": current_user.created_at,
        "last_login_at": current_user.last_login_at,
    }
