"""
Job model for tracking karaoke processing tasks.
"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import relationship

from ..database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING_AUDIO = "processing_audio"
    PROCESSING_STEMS = "processing_stems"
    EXTRACTING_LYRICS = "extracting_lyrics"
    FETCHING_LYRICS = "fetching_lyrics"
    CORRECTING_LYRICS = "correcting_lyrics"
    GENERATING_SUBTITLES = "generating_subtitles"
    GENERATING_VIDEO = "generating_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Task identification
    celery_task_id = Column(String(100), nullable=True)

    # Input
    original_filename = Column(String(500), nullable=True)
    input_file_path = Column(String(1000), nullable=True)

    # Job metadata
    song_title = Column(String(500), nullable=True)
    artist_name = Column(String(500), nullable=True)
    language = Column(String(50), nullable=True)

    # Status
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text, nullable=True)

    # Output
    output_video_path = Column(String(1000), nullable=True)
    output_video_url = Column(String(1000), nullable=True)
    output_audio_path = Column(String(1000), nullable=True)

    # Processing options (stored as JSON-like text)
    options_json = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Duration tracking
    processing_duration_seconds = Column(Float, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")

    def __repr__(self):
        return f"<Job {self.id} user={self.user_id} status={self.status}>"

    @property
    def status_display(self) -> str:
        status_labels = {
            JobStatus.PENDING: "Bekliyor",
            JobStatus.QUEUED: "Sıraya Alındı",
            JobStatus.PROCESSING_AUDIO: "Ses İşleniyor",
            JobStatus.PROCESSING_STEMS: "Stem Ayrımı",
            JobStatus.EXTRACTING_LYRICS: "Sözler Çıkarılıyor",
            JobStatus.FETCHING_LYRICS: "Sözler Getiriliyor",
            JobStatus.CORRECTING_LYRICS: "Sözler Düzeltiliyor",
            JobStatus.GENERATING_SUBTITLES: "Altyazı Oluşturuluyor",
            JobStatus.GENERATING_VIDEO: "Video Oluşturuluyor",
            JobStatus.COMPLETED: "Tamamlandı",
            JobStatus.FAILED: "Başarısız",
            JobStatus.CANCELED: "İptal Edildi",
        }
        return status_labels.get(self.status, self.status)
