from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from src.api.deps import require_api_key

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatIn(BaseModel):
    text: str
    client_external_id: str | None = None
    resource: str | None = None
    session: str | None = None


class ChatOut(BaseModel):
    reply: str


@router.post("", response_model=ChatOut, dependencies=[Depends(require_api_key)])
async def chat(inp: ChatIn):
    # Placeholder: next step будет подключение Chat Engine + Storage + LLM
    return ChatOut(reply=f"echo: {inp.text}")
