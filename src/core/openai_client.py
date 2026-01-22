from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import partial

import anyio

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _responses_create_sync(
    *,
    api_key: str,
    model: str,
    input_items: list[dict],
    timeout_sec: int = 30,
) -> dict:
    payload = {
        "model": model,
        "input": input_items,
        "store": False,
    }

    req = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read()
        return json.loads(raw.decode("utf-8"))


def extract_output_text(resp_json: dict) -> str:
    output = resp_json.get("output") or []
    texts: list[str] = []

    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            if item.get("role") != "assistant":
                continue
            content = item.get("content") or []
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                text = part.get("text")
                if ptype in ("output_text", "text") and isinstance(text, str) and text.strip():
                    texts.append(text.strip())

    return "\n".join(texts).strip()


async def call_openai_text(
    *,
    api_key: str,
    model: str,
    input_items: list[dict],
    timeout_sec: int = 30,
) -> str:
    try:
        fn = partial(
            _responses_create_sync,
            api_key=api_key,
            model=model,
            input_items=input_items,
            timeout_sec=timeout_sec,
        )
        resp_json = await anyio.to_thread.run_sync(fn)
        return extract_output_text(resp_json) or ""

    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        msg = f"OpenAI HTTP {getattr(e, 'code', 'unknown')}"
        if body:
            msg = f"{msg}: {body[:1200]}"
        raise RuntimeError(msg) from e

    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI URL error: {getattr(e, 'reason', e)}") from e

    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e.__class__.__name__}: {e}") from e
