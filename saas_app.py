"""
AI Karaoke Studio - SaaS Entry Point

Usage:
    # Development
    uvicorn saas_app:app --reload --port 8000

    # Production
    uvicorn saas_app:app --host 0.0.0.0 --port 8000 --workers 4
"""

from saas.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "saas_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
