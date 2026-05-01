from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.config import get_settings
from app.routers import admin, auth, context, evaluation, imports, links, maintenance, memory, metrics, projects, task_logs


settings = get_settings()
app = FastAPI(title=settings.app_name)
CONSOLE_DIR = Path(__file__).parent / "static" / "console"

app.include_router(projects.router)
app.include_router(auth.router)
app.include_router(memory.router)
app.include_router(context.router)
app.include_router(links.router)
app.include_router(maintenance.router)
app.include_router(task_logs.router)
app.include_router(evaluation.router)
app.include_router(metrics.router)
app.include_router(admin.router)
app.include_router(imports.router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/console")
@app.get("/console/")
def console_index() -> FileResponse:
    return FileResponse(CONSOLE_DIR / "index.html")


@app.get("/console/{path:path}")
def console_assets_or_spa(path: str) -> FileResponse:
    asset_path = (CONSOLE_DIR / path).resolve()
    if asset_path.is_file() and CONSOLE_DIR in asset_path.parents:
        return FileResponse(asset_path)
    return FileResponse(CONSOLE_DIR / "index.html")
