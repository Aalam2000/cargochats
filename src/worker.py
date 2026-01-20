from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from sqlalchemy import select

from src.models.resource import Resource, ResourceSettings
from src.models.session import Session, SessionSettings
from src.storage.db import get_db

from telethon import TelegramClient, events
from telethon.sessions import StringSession


SYNC_INTERVAL_SEC = int(os.getenv("WORKER_SYNC_INTERVAL_SEC", "5"))


@dataclass
class TgRuntime:
    cfg_sig: str
    client: TelegramClient
    stop: asyncio.Event
    task: asyncio.Task


def _cfg_sig(api_id: int, api_hash: str, session_string: str) -> str:
    # если настройки изменились — перезапускаем клиента
    return f"{api_id}:{api_hash}:{session_string}"


async def _get_db_once():
    """
    Берем один AsyncSession через существующий dependency get_db()
    и гарантированно закрываем.
    """
    agen = get_db()
    db = await agen.__anext__()
    try:
        yield db
    finally:
        await agen.aclose()


async def fetch_active_tg_sessions() -> Dict[int, Dict[str, Any]]:
    """
    Возвращает активные Telegram-сессии:
    session_id -> {api_id, api_hash, session_string}
    """
    async for db in _get_db_once():
        stmt = (
            select(
                Resource.id,
                Resource.kind,
                Resource.is_enabled,
                ResourceSettings.data,
                Session.id,
                Session.is_enabled,
                SessionSettings.is_enabled,
                SessionSettings.data,
            )
            .select_from(Resource)
            .join(ResourceSettings, ResourceSettings.resource_id == Resource.id)
            .join(Session, Session.resource_id == Resource.id)
            .join(SessionSettings, SessionSettings.session_id == Session.id)
            .where(Resource.kind == "telegram")
        )

        rows = (await db.execute(stmt)).all()

    out: Dict[int, Dict[str, Any]] = {}
    for (
        _resource_id,
        _kind,
        resource_enabled,
        rs_data,
        session_id,
        session_enabled,
        ss_enabled,
        ss_data,
    ) in rows:
        if not resource_enabled:
            continue
        if not session_enabled:
            continue
        if not ss_enabled:
            continue

        rs_data = rs_data or {}
        ss_data = ss_data or {}

        api_id = rs_data.get("api_id")
        api_hash = (rs_data.get("api_hash") or "").strip()

        is_activated = bool(ss_data.get("is_activated"))
        session_string = (ss_data.get("session_string") or "").strip()

        if not (api_id and api_hash and is_activated and session_string):
            continue

        out[int(session_id)] = {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "session_string": session_string,
        }

    return out


async def tg_echo_loop(session_id: int, client: TelegramClient, stop: asyncio.Event) -> None:
    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event: events.NewMessage.Event) -> None:
        # MVP: только приватные, чтобы не эхолотить группы/каналы
        if not event.is_private:
            return
        text = (event.raw_text or "").strip()
        if not text:
            return
        await event.reply(text)

    await client.connect()
    print(f"[worker][tg:{session_id}] connected")

    run_task = asyncio.create_task(client.run_until_disconnected())
    stop_task = asyncio.create_task(stop.wait())

    try:
        done, pending = await asyncio.wait(
            {run_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # если выключили — отключаемся
        if stop_task in done:
            await client.disconnect()

        for t in pending:
            t.cancel()

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        print(f"[worker][tg:{session_id}] stopped")


async def _stop_runtime(rt: TgRuntime) -> None:
    rt.stop.set()
    rt.task.cancel()
    try:
        await rt.task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[worker] stop error: {e.__class__.__name__}: {e}")
    try:
        await rt.client.disconnect()
    except Exception:
        pass


async def _sync_runtimes(runtimes: Dict[int, TgRuntime]) -> None:
    active = await fetch_active_tg_sessions()

    # stop removed / disabled / changed
    for sid, rt in list(runtimes.items()):
        cfg = active.get(sid)
        if not cfg:
            runtimes.pop(sid, None)
            await _stop_runtime(rt)
            continue

        sig = _cfg_sig(cfg["api_id"], cfg["api_hash"], cfg["session_string"])
        if sig != rt.cfg_sig:
            runtimes.pop(sid, None)
            await _stop_runtime(rt)

    # start new
    for sid, cfg in active.items():
        if sid in runtimes:
            continue

        stop = asyncio.Event()
        client = TelegramClient(
            StringSession(cfg["session_string"]),
            cfg["api_id"],
            cfg["api_hash"],
        )
        sig = _cfg_sig(cfg["api_id"], cfg["api_hash"], cfg["session_string"])
        task = asyncio.create_task(tg_echo_loop(sid, client, stop))

        runtimes[sid] = TgRuntime(cfg_sig=sig, client=client, stop=stop, task=task)

        def _cleanup(t: asyncio.Task, _sid: int = sid) -> None:
            rt2 = runtimes.get(_sid)
            if rt2 and rt2.task is t and t.done():
                # если упало само — убираем, на следующей синхронизации поднимем снова
                runtimes.pop(_sid, None)
                exc = t.exception()
                if exc:
                    print(f"[worker][tg:{_sid}] crashed: {exc.__class__.__name__}: {exc}")

        task.add_done_callback(_cleanup)


async def main_async() -> None:
    runtimes: Dict[int, TgRuntime] = {}
    print("[worker] started (telegram echo)")

    while True:
        try:
            await _sync_runtimes(runtimes)
        except Exception as e:
            print(f"[worker] sync error: {e.__class__.__name__}: {e}")
        await asyncio.sleep(SYNC_INTERVAL_SEC)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
