from fastapi import FastAPI

from app.config import get_settings
from app.routers import admin, auth, evaluation, imports, links, maintenance, memory, metrics, projects, task_logs


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(projects.router)
app.include_router(auth.router)
app.include_router(memory.router)
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
