from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.chatbot import ask_database

app = FastAPI(title="Maritime AI Chatbot")

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        response = ask_database(req.message)
        return {"response": response}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

