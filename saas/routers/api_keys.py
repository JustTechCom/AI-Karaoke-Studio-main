"""
API Keys router: manage API keys for programmatic access.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.api_key import APIKey
from ..auth import get_current_active_user, hash_api_key

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    name: str
    read_only: bool = False
    expires_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    read_only: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]


@router.get("")
async def list_api_keys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all API keys for the current user."""
    keys = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True,
    ).all()

    return {
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "is_active": k.is_active,
                "read_only": k.read_only,
                "last_used_at": k.last_used_at,
                "created_at": k.created_at,
                "expires_at": k.expires_at,
            }
            for k in keys
        ]
    }


@router.post("", status_code=201)
async def create_api_key(
    request: CreateKeyRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new API key."""
    # Check plan allows API access
    from ..config import SUBSCRIPTION_PLANS
    plan = current_user.current_plan
    if plan not in ("pro", "enterprise") and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="API erişimi Pro veya Kurumsal plan gerektiriyor",
        )

    # Limit number of keys
    key_count = db.query(APIKey).filter(
        APIKey.user_id == current_user.id,
        APIKey.is_active == True,
    ).count()

    max_keys = 5 if plan == "pro" else 20
    if key_count >= max_keys and not current_user.is_admin:
        raise HTTPException(
            status_code=400,
            detail=f"Maksimum API anahtarı sayısına ({max_keys}) ulaştınız",
        )

    raw_key, prefix = APIKey.generate_key()
    hashed = hash_api_key(raw_key)

    expires_at = None
    if request.expires_days:
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(days=request.expires_days)

    key = APIKey(
        user_id=current_user.id,
        name=request.name,
        key_prefix=prefix,
        hashed_key=hashed,
        read_only=request.read_only,
        expires_at=expires_at,
    )
    db.add(key)
    db.commit()
    db.refresh(key)

    # Return the raw key only once
    return {
        "id": key.id,
        "name": key.name,
        "key": raw_key,  # Only shown once!
        "key_prefix": key.key_prefix,
        "message": "API anahtarınızı kaydedin - bir daha gösterilmeyecek!",
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Revoke an API key."""
    key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.user_id == current_user.id,
    ).first()

    if not key:
        raise HTTPException(status_code=404, detail="API anahtarı bulunamadı")

    key.is_active = False
    db.commit()

    return {"message": "API anahtarı iptal edildi"}
