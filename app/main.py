# main.py - Application Startup --> App entry point 
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import engine
from app import models
from app.routes import auth, users, chat, map


from app.digital_twin.routes import router as twin_router
from app.digital_twin.twin_worker import start_twin_worker

import threading

from app.carbon.routes import router as carbon_router
# from digital_twin.twin_worker import start_twin_worker
# from app.digital_twin.twin_worker import start_twin_worker
# from services.piracy_service import router as piracy_router
from app.vessel_tracking.tracking import router as tracking_router
# from pydantic import BaseModel
# from app.chatbot import ask_database
# from anomaly_detection import router as anomaly_router
from app.anomaly_detection.anomaly import router as anomaly_router


from fastapi.middleware.cors import CORSMiddleware

models.Base.metadata.create_all(bind=engine) #SQLAlchemy checks models & Creates tables if not exist.

app = FastAPI(title="Maritime Digital Twin API")  #app = fastapi() --> FastAPI app starts.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy static frontend kept for backwards-compat during transition.
legacy_frontend_dir = Path(__file__).resolve().parent / "frontend"
if legacy_frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(legacy_frontend_dir), html=True), name="legacy_frontend")

# Vite (React + shadcn) build output: repo_root/frontend/dist
repo_root = Path(__file__).resolve().parent.parent
vite_dist_dir = repo_root / "frontend" / "dist"

@app.get("/ui", include_in_schema=False)
def ui():
    index = vite_dist_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"detail": "UI not built. Run `npm install` + `npm run build` in ./frontend."}

@app.get("/legacy-ui", include_in_schema=False)
def legacy_ui():
    legacy_index = legacy_frontend_dir / "index.html"
    if legacy_index.exists():
        return FileResponse(legacy_index)
    return {"detail": "Legacy UI not found."}

if vite_dist_dir.exists():
    # Serves /ui/assets/... and SPA fallback for /ui/*
    app.mount("/ui", StaticFiles(directory=str(vite_dist_dir), html=True), name="ui")

app.include_router(auth.router, prefix="/api", tags=["🔑 Authentication"])
app.include_router(users.router, prefix="/api", tags=["👤 User Management"])
app.include_router(chat.router, prefix="/api/chat", tags=["🤖 AI Chatbot"])
app.include_router(map.router, prefix="/api/map", tags=["🗺️ Map Analytics"])

@app.get("/")
def home():
    return {"message": "API is running successfully 🚀"}

# @app.post("/chat")
# def chat(req: ChatRequest):
#     response = ask_database(req.message)
#     return {"response": response}

# app.include_router(piracy_router)


app.include_router(twin_router, prefix="/twin")

# @app.on_event("startup")
# def start_background_tasks():

#     worker = threading.Thread(
#         target=start_twin_worker,
#         daemon=True
#     )

#     worker.start()
@app.on_event("startup")
def start_background_tasks():
    start_twin_worker()

app.include_router(carbon_router)

app.include_router(
    tracking_router,
    prefix="/api/tracking",
    tags=["🚢 Vessel Tracking"]
)


app.include_router(anomaly_router, prefix="/api/anomaly", tags=["⚠️  Anomaly Detection"])

# app.include_router(chatbot_router)