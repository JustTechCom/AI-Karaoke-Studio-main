"""
Admin router: user management, system stats, job monitoring.
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..database import get_db
from ..models.user import User
from ..models.subscription import Subscription
from ..models.job import Job, JobStatus
from ..models.usage import UsageRecord
from ..auth import get_admin_user
from ..config import SUBSCRIPTION_PLANS

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class UserAdminView(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_admin: bool
    plan: str
    created_at: datetime
    last_login_at: Optional[datetime]
    total_jobs: int

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    plan: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_system_stats(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Get system-wide statistics."""
    now = datetime.utcnow()
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)

    # User stats
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    new_users_30d = db.query(func.count(User.id)).filter(User.created_at >= last_30_days).scalar() or 0

    # Subscription stats
    plan_counts = {}
    for plan in SUBSCRIPTION_PLANS.keys():
        if plan == "free":
            # Count users without active paid subscription
            count = db.query(func.count(User.id)).filter(
                ~User.subscription.has(Subscription.plan != "free")
            ).scalar() or 0
        else:
            count = db.query(func.count(Subscription.id)).filter(
                Subscription.plan == plan,
                Subscription.status == "active",
            ).scalar() or 0
        plan_counts[plan] = count

    # Job stats
    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    jobs_30d = db.query(func.count(Job.id)).filter(Job.created_at >= last_30_days).scalar() or 0
    jobs_7d = db.query(func.count(Job.id)).filter(Job.created_at >= last_7_days).scalar() or 0
    completed_jobs = db.query(func.count(Job.id)).filter(Job.status == JobStatus.COMPLETED).scalar() or 0
    failed_jobs = db.query(func.count(Job.id)).filter(Job.status == JobStatus.FAILED).scalar() or 0
    active_jobs = db.query(func.count(Job.id)).filter(
        Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING_AUDIO, JobStatus.PROCESSING_STEMS,
                        JobStatus.EXTRACTING_LYRICS, JobStatus.GENERATING_VIDEO])
    ).scalar() or 0

    success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "new_last_30_days": new_users_30d,
            "by_plan": plan_counts,
        },
        "jobs": {
            "total": total_jobs,
            "last_30_days": jobs_30d,
            "last_7_days": jobs_7d,
            "completed": completed_jobs,
            "failed": failed_jobs,
            "active_now": active_jobs,
            "success_rate_pct": round(success_rate, 1),
        },
        "timestamp": now.isoformat(),
    }


@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 20,
    search: Optional[str] = None,
    plan: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all users with filtering."""
    query = db.query(User)

    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | (User.username.ilike(f"%{search}%"))
        )

    if plan:
        if plan == "free":
            query = query.filter(
                ~User.subscription.has(Subscription.plan != "free")
            )
        else:
            query = query.join(Subscription).filter(Subscription.plan == plan)

    total = query.count()
    users = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for user in users:
        total_jobs = db.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar() or 0
        result.append({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "plan": user.current_plan,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "total_jobs": total_jobs,
        })

    return {"users": result, "total": total, "page": page, "per_page": per_page}


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Get detailed user info."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    total_jobs = db.query(func.count(Job.id)).filter(Job.user_id == user_id).scalar() or 0
    completed_jobs = db.query(func.count(Job.id)).filter(
        Job.user_id == user_id, Job.status == JobStatus.COMPLETED
    ).scalar() or 0

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "plan": user.current_plan,
        "stripe_customer_id": user.stripe_customer_id,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "subscription": {
            "plan": user.subscription.plan if user.subscription else "free",
            "status": user.subscription.status if user.subscription else "active",
            "period_end": user.subscription.current_period_end if user.subscription else None,
        } if user.subscription else None,
        "stats": {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
        },
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Update user settings (admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if request.is_active is not None:
        user.is_active = request.is_active

    if request.is_admin is not None:
        user.is_admin = request.is_admin

    if request.plan is not None:
        if request.plan not in SUBSCRIPTION_PLANS:
            raise HTTPException(status_code=400, detail="Geçersiz plan")
        if not user.subscription:
            sub = Subscription(user_id=user.id, plan=request.plan, status="active")
            db.add(sub)
        else:
            user.subscription.plan = request.plan
            user.subscription.status = "active"

    db.commit()
    return {"message": "Kullanıcı güncellendi"}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Deactivate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı deaktif edemezsiniz")

    user.is_active = False
    db.commit()
    return {"message": "Hesap deaktif edildi"}


@router.get("/jobs")
async def list_all_jobs(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List all jobs in the system (admin view)."""
    query = db.query(Job)

    if status:
        try:
            query = query.filter(Job.status == JobStatus(status))
        except ValueError:
            pass

    if user_id:
        query = query.filter(Job.user_id == user_id)

    total = query.count()
    jobs = query.order_by(desc(Job.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for job in jobs:
        result.append({
            "id": job.id,
            "user_id": job.user_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "progress": job.progress,
            "song_title": job.song_title,
            "artist_name": job.artist_name,
            "original_filename": job.original_filename,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
        })

    return {"jobs": result, "total": total, "page": page, "per_page": per_page}


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Retry a failed job (admin only)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")
    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Yalnızca başarısız işler yeniden denenebilir")

    options = json.loads(job.options_json) if job.options_json else {}

    job.status = JobStatus.QUEUED
    job.progress = 0
    job.error_message = None
    job.completed_at = None
    db.commit()

    from ..tasks import process_karaoke_job
    task = process_karaoke_job.delay(
        job_id=job.id,
        user_id=job.user_id,
        input_file_path=job.input_file_path,
        options=options,
    )
    job.celery_task_id = task.id
    db.commit()

    return {"message": "İş yeniden kuyruğa alındı", "task_id": task.id}
