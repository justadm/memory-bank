from fastapi import FastAPI

from app.config import get_settings
from app.routers import links, maintenance, memory, projects


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.include_router(projects.router)
app.include_router(memory.router)
app.include_router(links.router)
app.include_router(maintenance.router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

