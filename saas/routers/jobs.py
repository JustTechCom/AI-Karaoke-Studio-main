"""
Jobs router: submit, track, download, and manage karaoke processing jobs.
"""

import json
import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..database import get_db
from ..models.job import Job, JobStatus
from ..models.user import User
from ..models.subscription import Subscription
from ..models.usage import UsageRecord, get_current_billing_period
from ..auth import get_current_active_user
from ..storage import storage
from ..config import settings, SUBSCRIPTION_PLANS
from ..tasks import process_karaoke_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    id: str
    status: str
    status_display: str
    progress: int
    original_filename: Optional[str]
    song_title: Optional[str]
    artist_name: Optional[str]
    output_video_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    per_page: int


# ─── Helpers ──────────────────────────────────────────────────────────────────

def check_quota(user: User, db: Session) -> None:
    """Check if user has remaining quota for this billing period."""
    plan = user.current_plan
    plan_config = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["free"])
    songs_limit = plan_config["songs_per_month"]

    if songs_limit == -1:  # Unlimited
        return

    # Count completed jobs this billing period
    period = get_current_billing_period()
    usage_count = db.query(func.count(UsageRecord.id)).filter(
        UsageRecord.user_id == user.id,
        UsageRecord.billing_period == period,
    ).scalar() or 0

    if usage_count >= songs_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Bu ay için şarkı kotanıza ({songs_limit}) ulaştınız. "
                   f"Planınızı yükseltmek için /pricing sayfasını ziyaret edin.",
        )


def _build_job_response(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "status_display": job.status_display,
        "progress": job.progress,
        "original_filename": job.original_filename,
        "song_title": job.song_title,
        "artist_name": job.artist_name,
        "output_video_url": job.output_video_url,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/submit", status_code=201)
async def submit_job(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    use_ai_correction: bool = Form(True),
    fetch_reference_lyrics: bool = Form(True),
    resolution: str = Form("1280x720"),
    fps: int = Form(24),
    font: str = Form("Arial"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Submit a new karaoke job."""
    # Check quota
    check_quota(current_user, db)

    # Validate file
    allowed_extensions = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma"}
    file_ext = Path(audio_file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya formatı: {file_ext}. "
                   f"İzin verilen: {', '.join(allowed_extensions)}",
        )

    # Check file size
    file_content = await audio_file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük ({file_size_mb:.1f}MB). "
                   f"Maksimum: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Check duration limit based on plan
    plan = current_user.current_plan
    plan_config = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["free"])
    max_resolution = plan_config["max_resolution"]

    # Enforce plan resolution limits
    plan_resolution_map = {
        "720p": ["640x480", "1280x720"],
        "1080p": ["640x480", "1280x720", "1920x1080"],
        "4k": ["640x480", "1280x720", "1920x1080", "3840x2160"],
    }
    allowed_resolutions = plan_resolution_map.get(max_resolution, ["1280x720"])
    if resolution not in allowed_resolutions:
        resolution = "1280x720"  # Default fallback

    # Create job record
    job = Job(
        user_id=current_user.id,
        original_filename=audio_file.filename,
        status=JobStatus.PENDING,
        progress=0,
        language=language,
    )
    db.add(job)
    db.flush()  # Get job ID

    # Save uploaded file
    try:
        input_path = storage.save_upload(
            current_user.id,
            job.id,
            file_content,
            audio_file.filename,
        )
        job.input_file_path = input_path
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Dosya kaydedilemedi: {str(e)}")

    # Build processing options
    options = {
        "language": language,
        "use_ai_correction": use_ai_correction,
        "fetch_reference_lyrics": fetch_reference_lyrics,
        "resolution": resolution,
        "fps": fps,
        "font": font,
    }
    job.options_json = json.dumps(options)
    db.commit()

    # Queue the Celery task
    try:
        task = process_karaoke_job.delay(
            job_id=job.id,
            user_id=current_user.id,
            input_file_path=input_path,
            options=options,
        )
        job.celery_task_id = task.id
        job.status = JobStatus.QUEUED
        db.commit()
    except Exception as e:
        # If Celery is unavailable, keep job as pending
        job.error_message = f"Kuyruk hatası: {str(e)}"
        db.commit()

    return {
        "job_id": job.id,
        "status": job.status.value,
        "message": "İş sıraya alındı",
    }


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    per_page: int = 10,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all jobs for the current user."""
    query = db.query(Job).filter(Job.user_id == current_user.id)

    if status:
        try:
            query = query.filter(Job.status == JobStatus(status))
        except ValueError:
            pass

    total = query.count()
    jobs = query.order_by(desc(Job.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return JobListResponse(
        jobs=[_build_job_response(j) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get job details."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")

    return _build_job_response(job)


@router.get("/{job_id}/download")
async def download_video(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Download the completed karaoke video."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Video henüz hazır değil")

    if not job.output_video_path or not os.path.exists(job.output_video_path):
        raise HTTPException(status_code=404, detail="Video dosyası bulunamadı")

    filename = f"{job.artist_name or 'Unknown'}_{job.song_title or 'karaoke'}.mp4"
    filename = "".join(c for c in filename if c.isalnum() or c in "_- .").strip()

    return FileResponse(
        path=job.output_video_path,
        media_type="video/mp4",
        filename=filename or "karaoke.mp4",
    )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Cancel a pending/queued job."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")

    if job.status not in (JobStatus.PENDING, JobStatus.QUEUED):
        raise HTTPException(status_code=400, detail="Yalnızca bekleyen işler iptal edilebilir")

    # Revoke Celery task
    if job.celery_task_id:
        try:
            from ..tasks import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
        except Exception:
            pass

    job.status = JobStatus.CANCELED
    job.completed_at = datetime.utcnow()
    db.commit()

    return {"message": "İş iptal edildi"}


@router.get("/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Lightweight status check for polling."""
    job = db.query(Job).filter(
        Job.id == job_id,
        Job.user_id == current_user.id,
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="İş bulunamadı")

    return {
        "job_id": job.id,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "status_display": job.status_display,
        "progress": job.progress,
        "output_video_url": job.output_video_url,
        "error_message": job.error_message,
    }
