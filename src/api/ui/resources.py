from __future__ import annotations

import time
import urllib.error
import urllib.request
from uuid import uuid4

import anyio
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, delete

from src.api.deps import require_company_from_token
from src.models.resource import Resource, ResourceSettings
from src.models.session import Session, SessionSettings
from src.storage.db import get_db
import logging


OPENAI_KEY_FIELD = "openai_api_key"

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


def _get_allowed_prompt_models() -> list[str]:
    """
    Берём список моделей из env OPENAI_ALLOWED_MODELS (csv).
    Если env пустой — возвращаем дефолт.
    """
    import os

    raw = (os.getenv("OPENAI_ALLOWED_MODELS") or "").strip()
    if not raw:
        return ["gpt-4o-mini"]

    items = [x.strip() for x in raw.split(",")]
    return [x for x in items if x]


async def _compute_resource_state(db, resource: Resource) -> str:
    """
    State values for UI list:
      - Active: telegram session activated + enabled
      - Readi: telegram session activated but disabled
      - False: not activated
    For non-telegram: Active if resource.is_enabled else False.
    """
    if resource.kind != "telegram":
        return "Active" if bool(getattr(resource, "is_enabled", False)) else "False"

    # telegram: derive from Session/SessionSettings
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    rs = result.scalar_one_or_none()
    rs_data = dict(rs.data or {}) if (rs and isinstance(rs.data, dict)) else {}
    session_id = rs_data.get("session_id")
    if not session_id:
        return "False"

    result = await db.execute(
        select(Session).where(
            Session.id == int(session_id),
            Session.resource_id == resource.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return "False"

    result = await db.execute(
        select(SessionSettings).where(SessionSettings.session_id == session.id)
    )
    ss = result.scalar_one_or_none()
    ss_data = dict(ss.data or {}) if (ss and isinstance(ss.data, dict)) else {}

    is_activated = bool(ss_data.get("is_activated")) and bool((ss_data.get("session_string") or "").strip())
    if not is_activated:
        return "False"

    return "Active" if bool(session.is_enabled) else "Readi"


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

    status_map: dict[int, str] = {}
    for r in items:
        status_map[r.id] = await _compute_resource_state(db, r)

    return templates.TemplateResponse(
        "ui/resources.html",
        {
            "request": request,
            "items": items,
            "status_map": status_map,
            "static_ts": int(time.time()),
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

    # state for table row
    if kind == "telegram":
        state = "False"
    else:
        state = "Active" if bool(getattr(resource, "is_enabled", False)) else "False"

    return JSONResponse({"id": resource.id, "status": state})


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

    # defaults for template context
    openai_has_key = False
    openai_key_mask = ""

    prompt_model = ""
    prompt_system_prompt = ""
    prompt_history_pairs = None
    prompt_google_sources: list[str] = []
    prompt_out_of_scope_enabled = False
    prompt_models = _get_allowed_prompt_models()

    telegram_api_id = None
    telegram_api_hash = ""
    telegram_has_hash = False
    telegram_api_hash_mask = ""
    telegram_openai_resource_id = None
    telegram_prompt_resource_id = None
    telegram_session_id = None
    telegram_session_is_enabled = False
    telegram_session_is_activated = False
    telegram_phone = ""

    openai_resources = []
    prompt_resources = []

    # load settings once (if exists)
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    data = dict(settings.data or {}) if (settings and isinstance(settings.data, dict)) else {}

    if resource.kind == "openai":
        api_key = (data.get(OPENAI_KEY_FIELD) or "").strip()
        if api_key:
            openai_has_key = True
            openai_key_mask = "*" * 24

    if resource.kind == "prompt":
        prompt_model = (data.get("model") or "")
        prompt_system_prompt = (data.get("system_prompt") or "")

        hp = data.get("history_pairs")
        if hp is not None:
            try:
                prompt_history_pairs = int(hp)
            except Exception:
                prompt_history_pairs = None

        gs = data.get("google_sources")
        if isinstance(gs, list):
            prompt_google_sources = [str(x) for x in gs if str(x).strip()]
        else:
            prompt_google_sources = []

        prompt_out_of_scope_enabled = bool(data.get("out_of_scope_enabled"))

    if resource.kind == "telegram":
        # current telegram values
        telegram_api_id = data.get("api_id")
        telegram_api_hash = (data.get("api_hash") or "")
        telegram_phone = data.get("phone")
        if telegram_api_hash:
            telegram_has_hash = True
            telegram_api_hash_mask = "*" * 16

        telegram_openai_resource_id = data.get("openai_resource_id")
        telegram_prompt_resource_id = data.get("prompt_resource_id")
        telegram_session_id = data.get("session_id")
        if telegram_session_id:
            result = await db.execute(
                select(Session).where(
                    Session.id == int(telegram_session_id),
                    Session.resource_id == resource.id,
                )
            )
            session = result.scalar_one_or_none()
            if session:
                telegram_session_is_enabled = bool(session.is_enabled)

                result = await db.execute(
                    select(SessionSettings).where(SessionSettings.session_id == session.id)
                )
                ss = result.scalar_one_or_none()
                if ss and isinstance(ss.data, dict):
                    telegram_session_is_activated = (
                        bool(ss.data.get("is_activated"))
                        and bool((ss.data.get("session_string") or "").strip())
                    )

        # lists for selects
        result = await db.execute(
            select(Resource)
            .where(
                Resource.company_id == company_id,
                Resource.kind == "openai",
            )
            .order_by(Resource.id)
        )
        openai_resources = result.scalars().all()

        result = await db.execute(
            select(Resource)
            .where(
                Resource.company_id == company_id,
                Resource.kind == "prompt",
            )
            .order_by(Resource.id)
        )
        prompt_resources = result.scalars().all()

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "resource": resource,

            "openai_has_key": openai_has_key,
            "openai_key_mask": openai_key_mask,
            "openai_resources": openai_resources,

            # prompt (важно: теперь всё прокидываем)
            "prompt_model": prompt_model,
            "prompt_system_prompt": prompt_system_prompt,
            "prompt_history_pairs": prompt_history_pairs,
            "prompt_google_sources": prompt_google_sources,
            "prompt_out_of_scope_enabled": prompt_out_of_scope_enabled,
            "prompt_models": prompt_models,
            "prompt_resources": prompt_resources,

            # telegram
            "telegram_api_id": telegram_api_id,
            "telegram_api_hash": telegram_api_hash,
            "telegram_has_hash": telegram_has_hash,
            "telegram_api_hash_mask": telegram_api_hash_mask,
            "telegram_openai_resource_id": telegram_openai_resource_id,
            "telegram_prompt_resource_id": telegram_prompt_resource_id,
            "telegram_session_id": telegram_session_id,
            "telegram_session_is_enabled": telegram_session_is_enabled,
            "telegram_session_is_activated": telegram_session_is_activated,
            "telegram_phone": telegram_phone,

            "static_ts": int(time.time()),
        },
    )


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
    history_pairs: int | None = None
    google_sources: list[str] | None = None
    out_of_scope_enabled: bool | None = None


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

    # model
    model = (payload.model or "").strip()
    if model:
        data["model"] = model
    else:
        data.pop("model", None)

    # system_prompt
    system_prompt = (payload.system_prompt or "").strip()
    if system_prompt:
        data["system_prompt"] = system_prompt
    else:
        data.pop("system_prompt", None)

    # history_pairs (0..50)
    hp = payload.history_pairs
    if hp is None:
        data.pop("history_pairs", None)
    else:
        if hp < 0 or hp > 50:
            raise HTTPException(status_code=400, detail="history_pairs must be 0..50")
        data["history_pairs"] = int(hp)

    # google_sources (clean list)
    gs = payload.google_sources
    if not gs:
        data.pop("google_sources", None)
    else:
        cleaned: list[str] = []
        seen = set()
        for x in gs:
            v = (str(x) or "").strip()
            if not v:
                continue
            if v in seen:
                continue
            seen.add(v)
            cleaned.append(v)
        if cleaned:
            data["google_sources"] = cleaned
        else:
            data.pop("google_sources", None)

    # out_of_scope_enabled (always stored as bool if provided)
    if payload.out_of_scope_enabled is None:
        data.pop("out_of_scope_enabled", None)
    else:
        data["out_of_scope_enabled"] = bool(payload.out_of_scope_enabled)

    settings.data = data
    await db.commit()
    return JSONResponse({"ok": True})


# Telegram endpoints вынесены (без правок внутри функций)
from src.resources.telegram import router as telegram_router
router.include_router(telegram_router)
