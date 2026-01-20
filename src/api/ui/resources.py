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

    # defaults for template context
    openai_has_key = False
    openai_key_mask = ""

    prompt_model = ""
    prompt_system_prompt = ""

    telegram_api_id = None
    telegram_api_hash = ""
    telegram_has_hash = False
    telegram_api_hash_mask = ""
    telegram_openai_resource_id = None
    telegram_prompt_resource_id = None
    telegram_session_id = None
    telegram_session_is_enabled = False
    telegram_session_is_activated = False

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
                    telegram_session_is_activated = bool(ss.data.get("is_activated"))

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

            "prompt_model": prompt_model,
            "prompt_system_prompt": prompt_system_prompt,
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


# --- TELEGRAM SETTINGS + SESSION ACTIVATION (REAL, via Telethon) ---

from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError


class TelegramSettingsIn(BaseModel):
    phone: str | None = None
    api_id: int | None = None
    api_hash: str | None = None  # None => keep existing, "" => clear
    openai_resource_id: int | None = None
    prompt_resource_id: int | None = None


@router.post("/resources/{resource_id}/telegram/save")
async def telegram_save(
        resource_id: int,
        payload: TelegramSettingsIn,
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    company_id = request.state.company_id

    # resource must exist and be telegram
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "telegram":
        raise HTTPException(status_code=400, detail="Resource is not telegram")

    # load settings
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    data = dict(settings.data or {})

    # phone (optional, stored to show in UI + reuse)
    if payload.phone is None:
        data.pop("phone", None)
    else:
        phone = (payload.phone or "").strip()
        if phone:
            data["phone"] = phone
        else:
            data.pop("phone", None)

    # validate & set api_id
    if payload.api_id is None:
        data.pop("api_id", None)
    else:
        if payload.api_id <= 0:
            raise HTTPException(status_code=400, detail="api_id must be > 0")
        data["api_id"] = int(payload.api_id)

    # validate & set/keep api_hash
    if payload.api_hash is not None:
        v = (payload.api_hash or "").strip()
        if v:
            data["api_hash"] = v
        else:
            data.pop("api_hash", None)

    # validate referenced resources belong to company + kind
    async def _check_ref(rid: int, kind: str) -> None:
        res = await db.execute(
            select(Resource).where(
                Resource.id == rid,
                Resource.company_id == company_id,
                Resource.kind == kind,
            )
        )
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"{kind}_resource_id invalid")

    if payload.openai_resource_id is None:
        data.pop("openai_resource_id", None)
    else:
        await _check_ref(int(payload.openai_resource_id), "openai")
        data["openai_resource_id"] = int(payload.openai_resource_id)

    if payload.prompt_resource_id is None:
        data.pop("prompt_resource_id", None)
    else:
        await _check_ref(int(payload.prompt_resource_id), "prompt")
        data["prompt_resource_id"] = int(payload.prompt_resource_id)

    settings.data = data
    await db.commit()
    return JSONResponse({"ok": True})


class TelegramSessionEnabledIn(BaseModel):
    is_enabled: bool


class TelegramActivationStartIn(BaseModel):
    phone: str


class TelegramActivationConfirmIn(BaseModel):
    code: str


async def _get_or_create_default_session_for_telegram(
        db,
        resource: Resource,
        settings: ResourceSettings,
) -> tuple[Session, SessionSettings]:
    data = dict(settings.data or {})

    # 1) try session_id from settings
    session = None
    session_id = data.get("session_id")
    if session_id:
        result = await db.execute(
            select(Session).where(
                Session.id == int(session_id),
                Session.resource_id == resource.id,
            )
        )
        session = result.scalar_one_or_none()

    # 2) try default by code
    if not session:
        result = await db.execute(
            select(Session).where(
                Session.resource_id == resource.id,
                Session.code == "default",
            )
        )
        session = result.scalar_one_or_none()

    # 3) create if missing
    if not session:
        session = Session(resource_id=resource.id, code="default", title="Telegram session")
        db.add(session)
        await db.flush()

    # ensure link in ResourceSettings.data
    if data.get("session_id") != session.id:
        data["session_id"] = session.id
        settings.data = data
        await db.flush()

    # ensure SessionSettings
    result = await db.execute(
        select(SessionSettings).where(SessionSettings.session_id == session.id)
    )
    ss = result.scalar_one_or_none()
    if not ss:
        ss = SessionSettings(session_id=session.id, data={})
        db.add(ss)
        await db.flush()

    return session, ss


def _get_telegram_creds_or_400(settings_data: dict) -> tuple[int, str]:
    api_id = settings_data.get("api_id")
    api_hash = (settings_data.get("api_hash") or "").strip()
    if not api_id or not api_hash:
        raise HTTPException(status_code=400, detail="telegram api_id and api_hash required")
    return int(api_id), api_hash


@router.post("/resources/{resource_id}/telegram/session/activation/start")
async def telegram_session_activation_start(
        resource_id: int,
        payload: TelegramActivationStartIn,
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    """
    REAL start:
    - sends Telegram code to phone via Telethon
    - stores phone_code_hash + pending StringSession in SessionSettings.data
    """
    company_id = request.state.company_id
    phone = (payload.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="phone required")

    # resource must exist and be telegram
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "telegram":
        raise HTTPException(status_code=400, detail="Resource is not telegram")

    # settings
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    data = dict(settings.data or {})
    api_id, api_hash = _get_telegram_creds_or_400(data)

    # persist phone in resource settings for UI convenience
    data["phone"] = phone
    settings.data = data
    await db.flush()

    session, ss = await _get_or_create_default_session_for_telegram(db, resource, settings)

    client = TelegramClient(StringSession(""), api_id, api_hash)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)

        ss_data = dict(ss.data or {})
        ss_data["phone"] = phone
        ss_data["phone_code_hash"] = sent.phone_code_hash
        ss_data["pending_session_string"] = client.session.save()
        ss_data["is_activated"] = False
        # do NOT auto-enable here
        ss.data = ss_data

        await db.commit()
        return JSONResponse(
            {
                "session_id": session.id,
                "is_enabled": bool(session.is_enabled),
                "is_activated": False,
            }
        )
    finally:
        await client.disconnect()


@router.post("/resources/{resource_id}/telegram/session/activation/confirm")
async def telegram_session_activation_confirm(
        resource_id: int,
        payload: TelegramActivationConfirmIn,
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    """
    REAL confirm:
    - validates code via Telethon sign_in
    - stores final StringSession in SessionSettings.data['session_string']
    - marks is_activated=True
    """
    company_id = request.state.company_id

    code = (payload.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="code required")

    # resource must exist and be telegram
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "telegram":
        raise HTTPException(status_code=400, detail="Resource is not telegram")

    # settings
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=400, detail="Settings not found")

    rs_data = dict(settings.data or {})
    api_id, api_hash = _get_telegram_creds_or_400(rs_data)

    session, ss = await _get_or_create_default_session_for_telegram(db, resource, settings)

    ss_data = dict(ss.data or {})
    phone = (ss_data.get("phone") or rs_data.get("phone") or "").strip()
    phone_code_hash = (ss_data.get("phone_code_hash") or "").strip()
    pending_session_string = (ss_data.get("pending_session_string") or "").strip()

    if not phone or not phone_code_hash or not pending_session_string:
        raise HTTPException(status_code=409, detail="ACTIVATION_NOT_STARTED")

    client = TelegramClient(StringSession(pending_session_string), api_id, api_hash)
    try:
        await client.connect()
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)

        # SUCCESS: store real session string
        ss_data["session_string"] = client.session.save()
        ss_data["is_activated"] = True
        ss_data["activated_at"] = datetime.now(timezone.utc).isoformat()

        # cleanup pending data
        ss_data.pop("phone_code_hash", None)
        ss_data.pop("pending_session_string", None)

        ss.data = ss_data

        # IMPORTANT: do NOT auto-enable; that is controlled by /set_enabled button
        await db.commit()

        return JSONResponse(
            {
                "session_id": session.id,
                "is_enabled": bool(session.is_enabled),
                "is_activated": True,
            }
        )

    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        raise HTTPException(status_code=400, detail="INVALID_OR_EXPIRED_CODE")
    except SessionPasswordNeededError:
        # if you need 2FA later, we add a third endpoint without renaming existing ones
        raise HTTPException(status_code=409, detail="2FA_REQUIRED")
    finally:
        await client.disconnect()


@router.post("/resources/{resource_id}/telegram/session/set_enabled")
async def telegram_session_set_enabled(
        resource_id: int,
        payload: TelegramSessionEnabledIn,
        request: Request,
        _: None = Depends(require_company_from_token),
        db=Depends(get_db),
):
    company_id = request.state.company_id

    # resource must exist and be telegram
    result = await db.execute(
        select(Resource).where(
            Resource.id == resource_id,
            Resource.company_id == company_id,
        )
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if resource.kind != "telegram":
        raise HTTPException(status_code=400, detail="Resource is not telegram")

    # settings
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    session, ss = await _get_or_create_default_session_for_telegram(db, resource, settings)

    ss_data = dict(ss.data or {})
    is_activated = bool(ss_data.get("is_activated"))
    has_session = bool((ss_data.get("session_string") or "").strip())

    # STRICT CONTROL:
    # cannot enable until реально активирована и есть session_string
    if payload.is_enabled:
        if not is_activated:
            raise HTTPException(status_code=409, detail="NOT_ACTIVATED")
        if not has_session:
            raise HTTPException(status_code=409, detail="NO_SESSION")

    session.is_enabled = bool(payload.is_enabled)
    ss.is_enabled = bool(payload.is_enabled)

    await db.commit()
    return JSONResponse(
        {
            "session_id": session.id,
            "is_enabled": bool(session.is_enabled),
            "is_activated": is_activated,
        }
    )
