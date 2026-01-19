from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, delete

from src.api.deps import require_company_from_token
from src.models.resource import Resource, ResourceSettings
from src.storage.db import get_db

import json
import urllib.request
import urllib.error

import anyio
from pydantic import BaseModel

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/resources", response_class=HTMLResponse)
async def resources_list(
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    # 🔴 если первый заход с token — чистим URL
    token = request.query_params.get("token")
    if token:
        response = RedirectResponse(url="/ui/resources", status_code=302)
        response.set_cookie(
            key="cargochats_token",
            value=str(token),
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return response

    company_id = request.state.company_id

    result = await db.execute(
        select(Resource)
        .where(Resource.company_id == company_id)
        .order_by(Resource.id)
    )
    items = result.scalars().all()

    return templates.TemplateResponse(
        "ui/resources.html",
        {
            "request": request,
            "items": items,
        },
    )


@router.post("/resources")
async def resource_create(
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    data = await request.json()
    kind = data.get("kind")
    title = data.get("title")

    if kind not in ("openai", "telegram", "web", "prompt"):
        raise HTTPException(status_code=400, detail="Invalid resource kind")

    if not title:
        raise HTTPException(status_code=400, detail="Title required")

    company_id = request.state.company_id

    resource = Resource(
        company_id=company_id,
        kind=kind,
        title=title,
        code=str(uuid4()),
    )
    db.add(resource)
    await db.flush()

    db.add(ResourceSettings(resource_id=resource.id))
    await db.commit()

    return JSONResponse({"id": resource.id})


@router.delete("/resources/{resource_id}")
async def resource_delete(
        resource_id: int,
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    company_id = request.state.company_id

    await db.execute(
        delete(Resource)
        .where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    await db.commit()

    return JSONResponse({"status": "ok"})

@router.get("/resources/{resource_id}", response_class=HTMLResponse)
async def resource_detail(
    resource_id: int,
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    template = f"resources/{resource.kind}.html"

    openai_has_key = False
    openai_key_mask = ""

    prompt_model = ""
    prompt_system_prompt = ""

    if resource.kind == "openai":
        result = await db.execute(
            select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
        )
        settings = result.scalar_one_or_none()
        api_key = ""
        if settings and isinstance(settings.data, dict):
            api_key = (settings.data.get("openai_api_key") or "").strip()

        if api_key:
            openai_has_key = True
            openai_key_mask = "*" * 24


        if resource.kind == "prompt":
            result = await db.execute(
                select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
            )
            settings = result.scalar_one_or_none()
            if settings and isinstance(settings.data, dict):
                prompt_model = (settings.data.get("model") or "")
                prompt_system_prompt = (settings.data.get("system_prompt") or "")

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "resource": resource,
            "openai_has_key": openai_has_key,
            "openai_key_mask": openai_key_mask,
            "prompt_model": prompt_model,
            "prompt_system_prompt": prompt_system_prompt,
        },
    )


OPENAI_KEY_FIELD = "openai_api_key"


class OpenAIKeyIn(BaseModel):
    api_key: str | None = None


def _check_openai_key_sync(api_key: str) -> tuple[bool, str | None]:
    """
    Самая простая проверка: запрос /v1/models.
    200 => ключ работает, 401/403 => не работает, остальное => ошибка OpenAI/сети.
    """
    req = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if getattr(resp, "status", 200) == 200:
                return True, None
            return False, f"OpenAI вернул статус {getattr(resp, 'status', 'unknown')}"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "Ключ не работает (401/403)"
        return False, f"OpenAI вернул {e.code}"
    except Exception as e:
        return False, f"Ошибка сети: {e.__class__.__name__}"


@router.post("/resources/{resource_id}/openai/key")
async def openai_key_save(
    resource_id: int,
    payload: OpenAIKeyIn,
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    # ресурс должен быть именно openai и принадлежать компании
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "openai":
        raise HTTPException(status_code=400, detail="Resource is not openai")

    api_key = (payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")

    # настройки должны быть (создаются при POST /resources), но страхуемся
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    data = dict(settings.data or {})
    data[OPENAI_KEY_FIELD] = api_key
    settings.data = data

    await db.commit()
    return JSONResponse({"ok": True})


@router.post("/resources/{resource_id}/openai/check")
async def openai_key_check(
    resource_id: int,
    payload: OpenAIKeyIn,
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    # проверяем доступ к ресурсу компании, и что он openai
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "openai":
        raise HTTPException(status_code=400, detail="Resource is not openai")

    api_key = (payload.api_key or "").strip()

    if not api_key:
        result = await db.execute(
            select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
        )
        settings = result.scalar_one_or_none()
        if settings and isinstance(settings.data, dict):
            api_key = (settings.data.get("openai_api_key") or "").strip()

    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")

    ok, err = await anyio.to_thread.run_sync(_check_openai_key_sync, api_key)
    if ok:
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": err})

class PromptSettingsIn(BaseModel):
    model: str | None = None
    system_prompt: str | None = None


@router.post("/resources/{resource_id}/prompt/save")
async def prompt_save(
    resource_id: int,
    payload: PromptSettingsIn,
    request: Request,
    _: None = Depends(require_company_from_token),
    db=Depends(get_db),
):
    company_id = request.state.company_id

    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "prompt":
        raise HTTPException(status_code=400, detail="Resource is not prompt")

    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    data = dict(settings.data or {})

    model = (payload.model or "").strip()
    if model:
        data["model"] = model
    else:
        data.pop("model", None)

    system_prompt = (payload.system_prompt or "").strip()
    if system_prompt:
        data["system_prompt"] = system_prompt
    else:
        data.pop("system_prompt", None)

    settings.data = data
    await db.commit()
    return JSONResponse({"ok": True})
