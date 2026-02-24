"""
Celery Worker Entry Point

Usage:
    celery -A celery_worker.celery_app worker --loglevel=info --queues=karaoke
"""

from saas.tasks import celery_app

if __name__ == "__main__":
    celery_app.start()
