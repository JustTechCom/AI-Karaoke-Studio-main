"""
Celery background tasks for karaoke processing pipeline.
"""

import json
import logging
import traceback
from datetime import datetime
from pathlib import Path

from celery import Celery

from .config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "karaoke_saas",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "saas.tasks.process_karaoke_job": {"queue": "karaoke"},
    },
)


def _update_job_status(job_id: str, status: str, progress: int, error: str = None):
    """Update job status in database."""
    try:
        from .database import SessionLocal
        from .models.job import Job, JobStatus

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus(status)
                job.progress = progress
                job.updated_at = datetime.utcnow()
                if error:
                    job.error_message = error
                if status == "processing_audio":
                    job.started_at = datetime.utcnow()
                if status in ("completed", "failed", "canceled"):
                    job.completed_at = datetime.utcnow()
                    if job.started_at:
                        duration = (datetime.utcnow() - job.started_at).total_seconds()
                        job.processing_duration_seconds = duration
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update job status {job_id}: {e}")


def _update_job_output(job_id: str, video_path: str, video_url: str, audio_path: str = None):
    """Update job output paths in database."""
    try:
        from .database import SessionLocal
        from .models.job import Job

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.output_video_path = video_path
                job.output_video_url = video_url
                if audio_path:
                    job.output_audio_path = audio_path
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update job output {job_id}: {e}")


def _track_usage(user_id: str, job_id: str):
    """Record usage for billing."""
    try:
        from .database import SessionLocal
        from .models.usage import UsageRecord, get_current_billing_period

        db = SessionLocal()
        try:
            period = get_current_billing_period()
            record = UsageRecord(
                user_id=user_id,
                job_id=job_id,
                billing_period=period,
                songs_processed=1,
            )
            db.add(record)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to track usage for user {user_id}: {e}")


@celery_app.task(bind=True, name="saas.tasks.process_karaoke_job", max_retries=0)
def process_karaoke_job(self, job_id: str, user_id: str, input_file_path: str, options: dict):
    """
    Main Celery task for processing a karaoke job.
    Runs the full pipeline: audio processing → stem separation →
    lyrics extraction → video generation.
    """
    logger.info(f"Starting karaoke job {job_id} for user {user_id}")

    try:
        # ── Stage 1: Audio Processing ──────────────────────────────────────
        _update_job_status(job_id, "processing_audio", 5)
        logger.info(f"[{job_id}] Stage 1: Audio processing")

        from modules.config import initialize_directories
        from modules.logging_config import configure_logging

        project_root, cache_dir, fonts_dir, output_dir = initialize_directories()
        configure_logging(verbose=False)

        # Create job-specific cache directory
        job_cache_dir = Path(input_file_path).parent / "cache"
        job_cache_dir.mkdir(parents=True, exist_ok=True)

        # Audio processing
        from modules.audio_processing.main import process_audio
        audio_result = process_audio(
            audio_file=input_file_path,
            working_dir=str(job_cache_dir),
            force_process=options.get("force_audio_processing", False),
        )
        song_title = audio_result.get("title", "Unknown")
        artist_name = audio_result.get("artist", "Unknown")

        # Update job metadata
        _update_job_meta(job_id, song_title, artist_name)
        _update_job_status(job_id, "processing_stems", 15)

        # ── Stage 2: Stem Separation ──────────────────────────────────────
        logger.info(f"[{job_id}] Stage 2: Stem separation")
        from modules.stem_processing.stem_separation.main import separate_stems
        from modules.stem_processing.stem_merging.main import merge_stems

        separate_stems(
            audio_file=input_file_path,
            working_dir=str(job_cache_dir),
            force_process=options.get("force_audio_processing", False),
        )
        merge_stems(working_dir=str(job_cache_dir))

        _update_job_status(job_id, "extracting_lyrics", 35)

        # ── Stage 3: Lyrics Extraction ────────────────────────────────────
        logger.info(f"[{job_id}] Stage 3: Extracting lyrics via Whisper")
        from modules.lyrics_processing.extract_lyrics.main import extract_lyrics

        extract_lyrics(
            working_dir=str(job_cache_dir),
            language=options.get("language"),
            force_transcription=options.get("force_transcription", False),
        )
        _update_job_status(job_id, "fetching_lyrics", 50)

        # ── Stage 4: Fetch Reference Lyrics (optional) ────────────────────
        if options.get("fetch_reference_lyrics", True):
            logger.info(f"[{job_id}] Stage 4: Fetching reference lyrics from Genius")
            try:
                from modules.lyrics_processing.search_lyrics.main import search_lyrics
                search_lyrics(
                    working_dir=str(job_cache_dir),
                    song_title=song_title,
                    artist_name=artist_name,
                )
            except Exception as e:
                logger.warning(f"[{job_id}] Failed to fetch reference lyrics: {e}")

        _update_job_status(job_id, "correcting_lyrics", 60)

        # ── Stage 5: AI Lyrics Correction (optional) ──────────────────────
        if options.get("use_ai_correction", True):
            logger.info(f"[{job_id}] Stage 5: AI lyrics correction")
            try:
                from modules.lyrics_processing.modify_lyrics.main import modify_lyrics
                modify_lyrics(working_dir=str(job_cache_dir))
            except Exception as e:
                logger.warning(f"[{job_id}] AI correction failed, continuing: {e}")

        _update_job_status(job_id, "generating_subtitles", 75)

        # ── Stage 6: Generate Subtitles ───────────────────────────────────
        logger.info(f"[{job_id}] Stage 6: Generating ASS subtitles")
        from modules import process_karaoke_subtitles

        process_karaoke_subtitles(
            output_path=job_cache_dir,
            font=options.get("font", "/app/fonts/Futura XBlkCnIt BT.ttf"),
            primary_color=options.get("primary_color", "Orange"),
            secondary_color=options.get("secondary_color", "White"),
            fontsize=options.get("font_size", 60),
            outline_size=options.get("outline", 3),
        )

        _update_job_status(job_id, "generating_video", 85)

        # ── Stage 7: Generate Video ───────────────────────────────────────
        logger.info(f"[{job_id}] Stage 7: Generating karaoke video")
        from modules.video_processing.main import generate_karaoke_video

        # Determine output path
        from .storage import storage
        safe_title = "".join(c for c in f"{artist_name}_{song_title}" if c.isalnum() or c in "_- ")[:50]
        output_filename = f"{safe_title}_karaoke.mp4"
        output_path = storage.get_output_path(user_id, job_id, output_filename)

        audio_path = job_cache_dir / "karaoke_audio.mp3"
        ass_path = job_cache_dir / "karaoke_subtitles.ass"

        generate_karaoke_video(
            audio_path=str(audio_path),
            ass_path=str(ass_path),
            output_path=str(output_path),
            resolution=options.get("resolution", "1280x720"),
            fps=options.get("fps", 24),
            bitrate=options.get("video_bitrate", "2000k"),
            audio_bitrate=options.get("audio_bitrate", "192k"),
        )

        # ── Complete ──────────────────────────────────────────────────────
        video_url = storage.get_file_url(str(output_path))
        _update_job_output(job_id, str(output_path), video_url)
        _update_job_status(job_id, "completed", 100)
        _track_usage(user_id, job_id)

        # Send completion email
        try:
            from .database import SessionLocal
            from .models.user import User
            db = SessionLocal()
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                from .email_service import send_job_completion_email
                send_job_completion_email(user.email, user.username, song_title, job_id)
            db.close()
        except Exception:
            pass

        logger.info(f"[{job_id}] Completed successfully")
        return {"job_id": job_id, "status": "completed", "video_url": video_url}

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"[{job_id}] Job failed: {error_msg}")
        logger.error(traceback.format_exc())
        _update_job_status(job_id, "failed", 0, error=error_msg)
        raise


def _update_job_meta(job_id: str, song_title: str, artist_name: str):
    """Update job song metadata in database."""
    try:
        from .database import SessionLocal
        from .models.job import Job

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.song_title = song_title
                job.artist_name = artist_name
                db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to update job meta {job_id}: {e}")
