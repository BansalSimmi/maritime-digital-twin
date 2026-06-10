# # app/routes/chatbot.py

# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from app.chatbot import ask_database

# router = APIRouter(prefix="/chatbot", tags=["🤖 Chatbot"])

# class ChatRequest(BaseModel):
#     message: str

# @router.post("/")
# def chat(req: ChatRequest):
#     try:
#         response = ask_database(req.message)
#         return {"response": response}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))