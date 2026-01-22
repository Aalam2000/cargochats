from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy import select

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from src.core.chat_engine import generate_reply
from src.core.queues import InboundMessage, SessionQueue
from src.models.resource import Resource, ResourceSettings
from src.models.session import Session, SessionSettings
from src.storage.db import get_db


SYNC_INTERVAL_SEC = int(os.getenv("WORKER_SYNC_INTERVAL_SEC", "5"))


@dataclass
class TgRuntime:
    cfg_sig: str
    client: TelegramClient
    stop: asyncio.Event
    task: asyncio.Task


def _cfg_sig(api_id: int, api_hash: str, session_string: str, openai_resource_id: int | None) -> str:
    return f"{api_id}:{api_hash}:{session_string}:{openai_resource_id or ''}"


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
    session_id -> {company_id, api_id, api_hash, session_string, openai_resource_id}
    """
    async for db in _get_db_once():
        stmt = (
            select(
                Resource.company_id,
                Resource.id,
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
        company_id,
        _resource_id,
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
        openai_resource_id = rs_data.get("openai_resource_id")

        is_activated = bool(ss_data.get("is_activated"))
        session_string = (ss_data.get("session_string") or "").strip()

        if not (api_id and api_hash and is_activated and session_string):
            continue

        out[int(session_id)] = {
            "company_id": int(company_id),
            "api_id": int(api_id),
            "api_hash": api_hash,
            "session_string": session_string,
            "openai_resource_id": int(openai_resource_id) if openai_resource_id else None,
        }

    return out


async def tg_openai_loop(session_id: int, cfg: Dict[str, Any], client: TelegramClient, stop: asyncio.Event) -> None:
    """
    1 Telegram-сессия = 1 очередь = 1 consumer (строгий порядок).
    + ставим "прочитано"
    + показываем "печатает..." пока формируем ответ
    """
    queue = SessionQueue(maxsize=0)

    async def _safe_read_ack(chat_id: int, message_id: int) -> None:
        try:
            await client.send_read_acknowledge(chat_id, max_id=message_id)
        except Exception:
            pass

    @client.on(events.NewMessage(incoming=True))
    async def _on_message(event: events.NewMessage.Event) -> None:
        if stop.is_set():
            return
        if not event.is_private:
            return

        msg = getattr(event, "message", None)
        if not msg:
            return

        text = (event.raw_text or "").strip()
        if not text:
            return

        chat_id = int(getattr(event, "chat_id", 0) or 0)
        message_id = int(getattr(msg, "id", 0) or 0)
        if not chat_id or not message_id:
            return

        # ✅ сразу ставим "прочитано" (не блокируем хендлер)
        asyncio.create_task(_safe_read_ack(chat_id, message_id))

        await queue.put(InboundMessage(chat_id=chat_id, message_id=message_id, text=text))

    async def _consumer() -> None:
        import traceback

        while not stop.is_set():
            try:
                inbound = await queue.get(timeout=0.5)
            except asyncio.TimeoutError:
                continue

            reply = ""
            try:
                print(f"[worker][tg:{session_id}] inbound chat_id={inbound.chat_id} msg_id={inbound.message_id}")

                # ✅ показываем "typing" пока идёт генерация ответа
                async with client.action(inbound.chat_id, "typing"):
                    async for db in _get_db_once():
                        reply = await generate_reply(
                            db,
                            company_id=int(cfg["company_id"]),
                            openai_resource_id=cfg.get("openai_resource_id"),
                            user_text=inbound.text,
                        )

            except Exception as e:
                tb = traceback.format_exc()
                print(f"[worker][tg:{session_id}] OPENAI_ERROR: {e.__class__.__name__}: {e}\n{tb}")
                msg = (str(e) or e.__class__.__name__).strip()
                reply = f"Ошибка OpenAI: {msg[:180]}"

            try:
                await client.send_message(inbound.chat_id, reply)
                print(f"[worker][tg:{session_id}] sent reply_len={len(reply or '')}")
            except Exception as e:
                print(f"[worker][tg:{session_id}] send error: {e.__class__.__name__}: {e}")
            finally:
                try:
                    queue.task_done()
                except Exception:
                    pass

    await client.connect()
    print(f"[worker][tg:{session_id}] connected")

    consumer_task = asyncio.create_task(_consumer())
    run_task = asyncio.create_task(client.run_until_disconnected())
    stop_task = asyncio.create_task(stop.wait())

    try:
        done, pending = await asyncio.wait(
            {run_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if stop_task in done:
            await client.disconnect()

        for t in pending:
            t.cancel()

    finally:
        stop.set()
        consumer_task.cancel()
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

        sig = _cfg_sig(cfg["api_id"], cfg["api_hash"], cfg["session_string"], cfg.get("openai_resource_id"))
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
        sig = _cfg_sig(cfg["api_id"], cfg["api_hash"], cfg["session_string"], cfg.get("openai_resource_id"))
        task = asyncio.create_task(tg_openai_loop(sid, cfg, client, stop))

        runtimes[sid] = TgRuntime(cfg_sig=sig, client=client, stop=stop, task=task)

        def _cleanup(t: asyncio.Task, _sid: int = sid) -> None:
            # при hot-reload задачи часто отменяются — это не ошибка
            if t.cancelled():
                return

            rt2 = runtimes.get(_sid)
            if not (rt2 and rt2.task is t and t.done()):
                return

            runtimes.pop(_sid, None)

            try:
                exc = t.exception()
            except asyncio.CancelledError:
                return

            if exc:
                print(f"[worker][tg:{_sid}] crashed: {exc.__class__.__name__}: {exc}")

        task.add_done_callback(_cleanup)


async def main_async() -> None:
    runtimes: Dict[int, TgRuntime] = {}

    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL_SEC)
        except asyncio.CancelledError:
            return


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        # нормальная остановка при watchfiles reload / Ctrl+C
        pass



if __name__ == "__main__":
    main()
