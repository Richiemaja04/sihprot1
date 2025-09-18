from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import create_tables, get_db
from routes.admin_routes import router as admin_router
from routes.teacher_routes import router as teacher_router
from routes.student_routes import router as student_router
from routes.auth_routes import router as auth_router
from utils.websocket_manager import websocket_manager
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Timetable Scheduler API...")
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
    yield
    # Shutdown
    logger.info("Shutting down Timetable Scheduler API...")

# Initialize FastAPI app
app = FastAPI(
    title="Timetable Scheduler API",
    description="AI-powered timetable scheduling system using Genetic Algorithm",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(teacher_router, prefix="/api/teacher", tags=["Teacher"])
app.include_router(student_router, prefix="/api/student", tags=["Student"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Timetable Scheduler API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

@app.websocket("/ws/{user_type}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_type: str, user_id: str):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket, user_type, user_id)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back for heartbeat
            await websocket.send_text(f"Heartbeat: {data}")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, user_type, user_id)

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",  # Changed from 0.0.0.0 to 127.0.0.1
        port=8000,
        reload=True,
        log_level="info"
    )