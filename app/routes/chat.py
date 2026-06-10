from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(tags=["Chatbot"])


class ChatRequest(BaseModel):
    message: str
    history: list = []


@router.post("")
def chat(req: ChatRequest):
    try:
        # Lazy import so missing optional LLM deps don't crash the whole API.
        from app.chatbot import ask_database

        return ask_database(req.message, req.history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
