from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.api.deps import require_company_from_token
from src.models.resource import Resource, ResourceSettings
from src.models.session import Session, SessionSettings
from src.storage.db import get_db

from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import SendCodeUnavailableError
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError


logging.getLogger("telethon").setLevel(logging.DEBUG)

router = APIRouter()


# --- TELEGRAM SETTINGS + SESSION ACTIVATION (REAL, via Telethon) ---


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
    company_id = request.state.company_id

    # 1) resource must exist and be telegram
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

    # 2) settings (ResourceSettings)
    result = await db.execute(
        select(ResourceSettings).where(ResourceSettings.resource_id == resource.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ResourceSettings(resource_id=resource.id, data={})
        db.add(settings)
        await db.flush()

    rs_data = dict(settings.data or {})

    # 3) phone: payload -> saved settings
    phone = ((getattr(payload, "phone", None) or rs_data.get("phone") or "")).strip()
    print(f"[tg_start] rid={resource_id} phone={phone!r}")
    if not phone:
        raise HTTPException(status_code=400, detail="phone required")

    # persist phone for UI convenience
    rs_data["phone"] = phone
    settings.data = rs_data
    await db.flush()

    # 4) creds
    api_id, api_hash = _get_telegram_creds_or_400(rs_data)

    # 5) session + session settings
    session, ss = await _get_or_create_default_session_for_telegram(db, resource, settings)
    ss_data = dict(ss.data or {})

    # --- GUARDS (ключевое) ---
    # A) already activated -> do nothing
    if bool(ss_data.get("is_activated")) and (ss_data.get("session_string") or "").strip():
        return JSONResponse(
            {
                "detail": "ALREADY_ACTIVATED",
                "session_id": session.id,
                "is_enabled": bool(session.is_enabled),
                "is_activated": True,
            }
        )

    # B) activation already started recently -> do not resend (иначе быстро словишь SendCodeUnavailableError)
    now = int(time.time())
    started_at = int(ss_data.get("activation_started_at") or 0)
    pending_hash = (ss_data.get("phone_code_hash") or "").strip()
    pending_session_string = (ss_data.get("pending_session_string") or "").strip()

    PENDING_TTL_SECONDS = 120
    if pending_hash and pending_session_string and started_at and (now - started_at) < PENDING_TTL_SECONDS:
        return JSONResponse(
            {
                "detail": "ALREADY_STARTED",
                "session_id": session.id,
                "is_enabled": bool(session.is_enabled),
                "is_activated": False,
            }
        )

    # 6) telethon send code
    client = TelegramClient(StringSession(""), api_id, api_hash)
    try:
        await client.connect()

        t0 = time.monotonic()
        sent = await client.send_code_request(phone)
        dt_ms = int((time.monotonic() - t0) * 1000)

        # sent.type is IMPORTANT: SentCodeTypeApp means "code delivered INSIDE Telegram app" (not SMS)
        sent_type = type(sent.type).__name__ if getattr(sent, "type", None) else None
        next_type = type(sent.next_type).__name__ if getattr(sent, "next_type", None) else None
        code_len = getattr(sent, "type", None).length if getattr(sent, "type", None) else None
        timeout = getattr(sent, "timeout", None)

        print(
            f"[tg_start] ok rid={resource_id} dt_ms={dt_ms} sent_type={sent_type} "
            f"next_type={next_type} code_len={code_len} timeout={timeout} hash={sent.phone_code_hash!r}"
        )

        ss_data["phone"] = phone
        ss_data["phone_code_hash"] = sent.phone_code_hash
        ss_data["pending_session_string"] = client.session.save()
        ss_data["activation_started_at"] = now
        ss_data["is_activated"] = False
        ss.data = ss_data

        await db.commit()
        return JSONResponse(
            {
                "detail": "CODE_SENT",
                "session_id": session.id,
                "is_enabled": bool(session.is_enabled),
                "is_activated": False,
                "sent_type": sent_type,
                "next_type": next_type,
                "code_len": code_len,
                "timeout": timeout,
            }
        )

    except FloodWaitError as e:
        # Telegram explicitly says "wait N seconds"
        await db.rollback()
        raise HTTPException(status_code=429, detail=f"FLOOD_WAIT:{getattr(e, 'seconds', 0)}")

    except SendCodeUnavailableError:
        # You exhausted available resend options (обычно из-за частых повторов)
        await db.rollback()
        raise HTTPException(status_code=429, detail="SEND_CODE_UNAVAILABLE")

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
