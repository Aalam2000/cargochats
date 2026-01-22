from __future__ import annotations

import os
import uvicorn

from fastapi import FastAPI, Request, HTTPException
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.api.routes_health import router as health_router
from src.api.routes_chat import router as chat_router
from src.api.routes_settings import router as settings_router
from src.api.ui.router import router as ui_router
from src.api.public.router import router as public_router


CRM_HOME_URL = "https://crm.dadaexpo.ru/"

app = FastAPI(title="CargoChats")

# статика
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    """
    UI (GET) при 401/403 -> редирект на CRM + чистим cookie.
    UI (POST/AJAX) при 401/403 -> JSON 401/403 + чистим cookie (клиентский fetch перехватит).
    Остальное -> дефолтный обработчик.
    """
    if exc.status_code in (401, 403):
        is_ui = request.url.path.startswith("/ui")
        if is_ui:
            # сброс cookie при любом auth fail
            if request.method.upper() == "GET":
                resp = RedirectResponse(url=CRM_HOME_URL, status_code=302)
                resp.delete_cookie("cargochats_token", path="/")
                return resp

            resp = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            resp.delete_cookie("cargochats_token", path="/")
            return resp

        # non-UI: стандартный JSON
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    """
    Опционально: в PROD любые 500 на UI GET -> редирект на CRM.
    В DEV оставляем стандартное поведение (чтобы видеть traceback).
    """
    settings = get_settings()
    if settings.ENV != "dev" and request.url.path.startswith("/ui") and request.method.upper() == "GET":
        resp = RedirectResponse(url=CRM_HOME_URL, status_code=302)
        resp.delete_cookie("cargochats_token", path="/")
        return resp

    # default: пробрасываем стандартный 500
    raise exc


# корень → ресурсы
@app.get("/")
def root():
    return RedirectResponse(url="/ui/resources")


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
