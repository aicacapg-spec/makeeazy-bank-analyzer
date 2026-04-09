"""
MakeEazy Bank Statement Analyzer — FastAPI Application
Zero-cost, self-hosted bank statement analysis platform for CA firms.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import upload, documents, analysis, settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    print(f"[START] Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    init_db()
    print("[OK] Database initialized")
    yield
    print("[STOP] Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Bank Statement Analysis Platform for CA Firms — Zero Cost, Self-Hosted",
    lifespan=lifespan,
)

# ─── CORS ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ───
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(analysis.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["Settings"])


# ─── Health Check ───
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ─── Serve Frontend Static Files ───
# Try multiple paths: local dev vs Render deployment
_candidates = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "frontend", "dist"),
    "/opt/render/project/src/frontend/dist",
]
FRONTEND_DIR = None
for _p in _candidates:
    if os.path.exists(_p):
        FRONTEND_DIR = _p
        print(f"[STATIC] Serving frontend from: {_p}")
        break

if not FRONTEND_DIR:
    print(f"[STATIC] No frontend dist found. Candidates: {_candidates}")

if FRONTEND_DIR and os.path.exists(os.path.join(FRONTEND_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve React SPA — all non-API routes go to index.html."""
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
