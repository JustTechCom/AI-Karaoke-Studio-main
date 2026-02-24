"""
File storage service.
Supports local filesystem and AWS S3.
"""

import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Optional, BinaryIO

from .config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Handles file storage for user uploads and job outputs."""

    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.local_base = settings.STORAGE_LOCAL_PATH
        self.local_base.mkdir(parents=True, exist_ok=True)

    def get_user_dir(self, user_id: str) -> Path:
        """Get per-user storage directory."""
        user_dir = self.local_base / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def get_job_dir(self, user_id: str, job_id: str) -> Path:
        """Get job-specific directory."""
        job_dir = self.get_user_dir(user_id) / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def save_upload(self, user_id: str, job_id: str, file_content: bytes, filename: str) -> str:
        """Save an uploaded file. Returns the storage path."""
        job_dir = self.get_job_dir(user_id, job_id)

        # Sanitize filename
        safe_filename = self._sanitize_filename(filename)
        file_path = job_dir / "input" / safe_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(file_content)

        logger.info(f"Saved upload: {file_path}")
        return str(file_path)

    def get_output_path(self, user_id: str, job_id: str, filename: str) -> Path:
        """Get path for job output files."""
        job_dir = self.get_job_dir(user_id, job_id)
        output_dir = job_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / filename

    def get_file_url(self, file_path: str) -> str:
        """Convert a storage path to a downloadable URL."""
        if self.backend == "local":
            # Serve via /files/ endpoint
            relative = Path(file_path).relative_to(self.local_base)
            return f"{settings.APP_URL}/files/{relative}"
        elif self.backend == "s3":
            return self._get_s3_url(file_path)
        return file_path

    def delete_job_files(self, user_id: str, job_id: str) -> bool:
        """Delete all files for a job."""
        try:
            job_dir = self.get_job_dir(user_id, job_id)
            if job_dir.exists():
                shutil.rmtree(job_dir)
            return True
        except Exception as e:
            logger.error(f"Failed to delete job files {job_id}: {e}")
            return False

    def get_file_size_mb(self, file_path: str) -> float:
        """Get file size in MB."""
        try:
            size_bytes = os.path.getsize(file_path)
            return size_bytes / (1024 * 1024)
        except Exception:
            return 0.0

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove dangerous characters from filename."""
        import re
        # Keep only safe characters
        safe = re.sub(r'[^\w\-_. ]', '', filename)
        safe = safe.strip()
        if not safe:
            safe = "upload"
        return safe

    def _get_s3_url(self, key: str) -> str:
        """Get S3 pre-signed URL (placeholder for S3 implementation)."""
        return f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"


# Singleton instance
storage = StorageService()
