"""
PATH: src/api/public/tilda.py
PURPOSE: Public endpoint for Tilda widget: POST /public/tilda/chat. Validates widget_token, writes messages, returns reply.
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter(prefix="/tilda")


class TildaChatIn(BaseModel):
    widget_token: str
    external_client_id: str
    text: str


class TildaChatOut(BaseModel):
    reply: str


@router.post("/chat", response_model=TildaChatOut)
async def tilda_chat(inp: TildaChatIn):
    # TODO:
    # 1) resolve resource by widget_token
    # 2) resolve/create client + identity
    # 3) resolve/create dialog
    # 4) store inbound/outbound messages
    # 5) return LLM reply (for now echo)
    return TildaChatOut(reply=f"echo: {inp.text}")
