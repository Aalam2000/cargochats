from __future__ import annotations

import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.routes_health import router as health_router
from src.api.routes_chat import router as chat_router
from src.api.routes_settings import router as settings_router
from src.api.ui.router import router as ui_router
from src.api.public.router import router as public_router


app = FastAPI(title="CargoChats")

# статика
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

# API
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(settings_router)

# UI / public
app.include_router(ui_router)
app.include_router(public_router)


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
