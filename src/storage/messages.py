from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.client import Client, ClientIdentity
from src.models.dialog import Dialog
from src.models.message import Message


def _norm_session_id(session_id: int | None) -> int | None:
    try:
        sid = int(session_id) if session_id is not None else None
    except Exception:
        return None
    return sid if sid and sid > 0 else None


async def _resolve_client(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    kind: str,
    external_id: str,
) -> Client | None:
    stmt = (
        select(Client)
        .join(ClientIdentity, ClientIdentity.client_id == Client.id)
        .where(
            Client.company_id == int(company_id),
            Client.is_enabled.is_(True),
            ClientIdentity.resource_id == int(resource_id),
            ClientIdentity.kind == str(kind),
            ClientIdentity.external_id == str(external_id),
            ClientIdentity.is_enabled.is_(True),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _resolve_or_create_client(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    kind: str,
    external_id: str,
    meta: dict[str, Any] | None = None,
) -> Client:
    client = await _resolve_client(
        db,
        company_id=company_id,
        resource_id=resource_id,
        kind=kind,
        external_id=external_id,
    )
    if client:
        return client

    # ВАЖНО: clients имеет уникальность (company_id, code) — делаем код с префиксом, чтобы не конфликтовал между ресурсами.
    client_code = f"{kind}:{int(resource_id)}:{external_id}"[:64]
    client = Client(
        company_id=int(company_id),
        code=client_code,
        meta=meta or {"source": kind},
    )
    db.add(client)
    await db.flush()  # получить client.id

    ident = ClientIdentity(
        client_id=int(client.id),
        resource_id=int(resource_id),
        external_id=str(external_id),
        kind=str(kind),
        meta={},
    )
    db.add(ident)
    await db.flush()

    return client


async def _resolve_dialog(
    db: AsyncSession,
    *,
    company_id: int,
    client_id: int,
) -> Dialog | None:
    stmt = (
        select(Dialog)
        .where(
            Dialog.company_id == int(company_id),
            Dialog.client_id == int(client_id),
            Dialog.status == "open",
            Dialog.is_enabled.is_(True),
        )
        .order_by(Dialog.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _resolve_or_create_dialog(
    db: AsyncSession,
    *,
    company_id: int,
    client_id: int,
    dialog_meta: dict[str, Any] | None = None,
) -> Dialog:
    dialog = await _resolve_dialog(db, company_id=company_id, client_id=client_id)
    if dialog:
        return dialog

    dialog = Dialog(
        company_id=int(company_id),
        client_id=int(client_id),
        meta=dialog_meta or {},
    )
    db.add(dialog)
    await db.flush()
    return dialog


async def save_inbound(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    session_id: int | None,
    chat_id: int,
    tg_message_id: int,
    text: str,
) -> Message:
    """
    Telegram -> система: сохраняем in/user.
    Привязка: company (через dialog.company_id) + resource_id + session_id + chat_id (через client_identity external_id).
    """
    sid = _norm_session_id(session_id)
    external_id = str(int(chat_id))
    client = await _resolve_or_create_client(
        db,
        company_id=company_id,
        resource_id=resource_id,
        kind="tg",
        external_id=external_id,
        meta={"source": "tg"},
    )
    dialog = await _resolve_or_create_dialog(
        db,
        company_id=company_id,
        client_id=int(client.id),
        dialog_meta={"resource_id": int(resource_id), "chat_id": external_id, "session_id": sid},
    )

    msg = Message(
        dialog_id=int(dialog.id),
        direction="in",
        text=(text or "").strip(),
        resource_id=int(resource_id),
        session_id=sid,
        meta={"chat_id": external_id, "tg_message_id": int(tg_message_id)},
    )
    db.add(msg)
    await db.commit()
    return msg


async def save_outbound(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    session_id: int | None,
    chat_id: int,
    text: str,
    tg_message_id: int | None = None,
) -> Message:
    """
    система -> Telegram: сохраняем out/assistant.
    """
    sid = _norm_session_id(session_id)
    external_id = str(int(chat_id))

    client = await _resolve_or_create_client(
        db,
        company_id=company_id,
        resource_id=resource_id,
        kind="tg",
        external_id=external_id,
        meta={"source": "tg"},
    )
    dialog = await _resolve_or_create_dialog(
        db,
        company_id=company_id,
        client_id=int(client.id),
        dialog_meta={"resource_id": int(resource_id), "chat_id": external_id, "session_id": sid},
    )

    meta = {"chat_id": external_id}
    if tg_message_id:
        meta["tg_message_id"] = int(tg_message_id)

    msg = Message(
        dialog_id=int(dialog.id),
        direction="out",
        text=(text or "").strip(),
        resource_id=int(resource_id),
        session_id=sid,
        meta=meta,
    )
    db.add(msg)
    await db.commit()
    return msg


async def load_history(
    db: AsyncSession,
    *,
    company_id: int,
    resource_id: int,
    session_id: int | None,
    chat_id: int,
    limit_messages: int,
    exclude_message_id: int | None = None,
) -> list[Message]:
    """
    Возвращает последние сообщения (in/out) по ключу (company_id, resource_id, session_id, chat_id).
    Сортировка: по возрастанию времени (готово для OpenAI).
    """
    if not limit_messages or limit_messages <= 0:
        return []

    sid = _norm_session_id(session_id)
    external_id = str(int(chat_id))

    client = await _resolve_client(
        db,
        company_id=company_id,
        resource_id=resource_id,
        kind="tg",
        external_id=external_id,
    )
    if not client:
        return []

    dialog = await _resolve_dialog(db, company_id=company_id, client_id=int(client.id))
    if not dialog:
        return []

    stmt = (
        select(Message)
        .where(
            Message.dialog_id == int(dialog.id),
            Message.is_deleted.is_(False),
            Message.resource_id == int(resource_id),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(int(limit_messages))
    )

    if sid is None:
        stmt = stmt.where(Message.session_id.is_(None))
    else:
        stmt = stmt.where(Message.session_id == sid)

    if exclude_message_id:
        stmt = stmt.where(Message.id != int(exclude_message_id))

    msgs = (await db.execute(stmt)).scalars().all()
    msgs.reverse()  # asc
    return msgs
