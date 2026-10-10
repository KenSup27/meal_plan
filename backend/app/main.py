import base64
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.core.config import settings
from backend.app.repositories.base import RepositoryError


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.exception_handler(RepositoryError)
async def repository_error(_request, exc: RepositoryError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.get("/runtime-config.js", include_in_schema=False)
def runtime_config() -> Response:
    key = settings.supabase_anon_key or ""
    public_key = key.startswith("sb_publishable_")
    if key.count(".") == 2:
        try:
            claims = json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "=="))
            public_key = claims.get("role") == "anon"
        except (ValueError, TypeError):
            public_key = False
    config = {"url": settings.supabase_url or "", "publishableKey": key if public_key else ""}
    return Response("window.MEAL_PREP_SUPABASE = " + json.dumps(config) + ";", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
