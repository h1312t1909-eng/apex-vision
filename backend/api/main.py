"""
FastAPI Application Entry Point & Lifecycle Orchestrator.

Responsibilities:
1. Initialize FastAPI application with CORS middleware.
2. Execute database schema migrations and pgvector extension checks on startup.
3. Discover registered classrooms and initialize dedicated camera ingestion threads.
4. Launch background recognition inference worker loop.
5. Provide live MJPEG streaming endpoint for frontend CCTV video feeds.
6. Register all REST API routers and WebSocket endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database.connection import engine, SessionLocal, run_migrations
from backend.database.models import Classroom, Period
from backend.camera_ingestion.camera_manager import CameraManager
from backend.recognition.pipeline import RecognitionPipeline
from backend.attendance.attendance_processor import AttendanceProcessor
from backend.attendance.period_service import PeriodService
from backend.api.websocket_manager import ws_manager

# Import API Routers
from backend.api.routers.students_router import router as students_router
from backend.api.routers.classrooms_router import router as classrooms_router
from backend.api.routers.periods_router import router as periods_router
from backend.api.routers.attendance_router import router as attendance_router
from backend.api.routers.reports_router import router as reports_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cctv_attendance.main")

# Instantiate Core System Components
camera_manager = CameraManager()
recognition_pipeline = RecognitionPipeline()
attendance_processor = AttendanceProcessor()


async def background_recognition_worker():
    """
    Continuous background loop that grabs synchronized CCTV frames,
    executes SCRFD + MiniFASNet + ArcFace pipeline, updates attendance state, and broadcasts
    updates over WebSockets to React dashboards.
    """
    logger.info("[Worker] Starting CCTV background recognition loop...")
    loop = asyncio.get_event_loop()

    while True:
        try:
            # Non-blocking poll in executor to avoid blocking FastAPI event loop
            frame_data = await loop.run_in_executor(None, camera_manager.get_next_frame, False, 0.2)
            if frame_data is None:
                await asyncio.sleep(0.05)
                continue

            # Run recognition and attendance within a dedicated database session
            def process_in_thread():
                db: Session = SessionLocal()
                try:
                    # 1. Resolve active period
                    period = PeriodService.get_active_period(db, frame_data.classroom_id, frame_data.timestamp)
                    period_id = period.id if period else None

                    # 2. Run multi-face detection, anti-spoofing, and ArcFace pgvector search
                    frame_result = recognition_pipeline.process_frame(db, frame_data, period_id=period_id)

                    # 3. Process attendance, deduplication, entry/exit tracking
                    serialized_updates = []
                    if period_id is not None:
                        updated_records = attendance_processor.process_frame_recognition(db, frame_result)
                        for att in updated_records:
                            serialized_updates.append({
                                "record_id": att.id,
                                "student_id": att.student_id,
                                "student_name": att.student.name if att.student else "",
                                "roll_no": att.student.roll_no if att.student else "",
                                "status": att.status,
                                "confidence_score": att.confidence_score,
                                "entry_time": att.entry_time.isoformat() if att.entry_time else None,
                                "exit_time": att.exit_time.isoformat() if att.exit_time else None,
                                "marked_by": att.marked_by,
                                "period_id": att.period_id,
                                "updated_at": att.updated_at.isoformat() if att.updated_at else datetime.utcnow().isoformat()
                            })

                    return frame_result, serialized_updates, period_id
                finally:
                    db.close()

            frame_result, serialized_updates, period_id = await loop.run_in_executor(None, process_in_thread)

            # 4. Broadcast live visual detections (bounding boxes, spoof alerts) to dashboard
            if frame_result.recognitions:
                for rec in frame_result.recognitions:
                    event_payload = {
                        "event_type": "spoof_alert" if rec.is_spoof else "recognition",
                        "classroom_id": frame_data.classroom_id,
                        "period_id": period_id,
                        "timestamp": frame_data.timestamp.isoformat(),
                        "data": {
                            "bbox": rec.bbox,
                            "detector_confidence": rec.detector_confidence,
                            "is_spoof": rec.is_spoof,
                            "liveness_score": rec.liveness_score,
                            "student_id": rec.student_id,
                            "student_name": rec.match_result.name,
                            "roll_no": rec.match_result.roll_no,
                            "confidence_score": rec.confidence_score,
                            "status_tier": rec.status_tier
                        }
                    }
                    await ws_manager.broadcast_to_classroom(frame_data.classroom_id, event_payload)

            # 5. Broadcast confirmed/needs_review attendance updates
            for update in serialized_updates:
                await ws_manager.broadcast_to_classroom(
                    frame_data.classroom_id,
                    {
                        "event_type": "attendance_update",
                        "classroom_id": frame_data.classroom_id,
                        "period_id": update["period_id"],
                        "timestamp": update["updated_at"],
                        "data": update
                    }
                )

        except asyncio.CancelledError:
            logger.info("[Worker] Inference worker task cancelled.")
            break
        except Exception as exc:
            logger.error(f"[Worker] Unexpected error in recognition loop: {exc}")
            await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager: starts DB migrations, camera stream threads, and background workers on boot.
    """
    logger.info("Initializing CCTV Automated Attendance Backend...")
    try:
        run_migrations()
        logger.info("[Startup] Database schema & pgvector extensions checked/applied.")
    except Exception as exc:
        logger.warning(f"[Startup] Migration runner warning (check DB connection): {exc}")

    # Discover registered classrooms from database and launch camera threads
    db = SessionLocal()
    try:
        classrooms = db.query(Classroom).all()
        for cr in classrooms:
            camera_manager.register_camera(
                classroom_id=cr.id,
                camera_url=cr.camera_rtsp_url,
                target_fps=2.0
            )
            camera_manager.start_camera(cr.id)
        logger.info(f"[Startup] Launched camera ingestion threads for {len(classrooms)} classroom(s).")
    except Exception as exc:
        logger.error(f"[Startup] Error loading classroom camera configurations: {exc}")
    finally:
        db.close()

    # Launch background computer vision inference worker task
    worker_task = asyncio.create_task(background_recognition_worker())

    yield

    # Shutdown sequence
    logger.info("Shutting down CCTV Attendance Backend...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    camera_manager.stop_all()
    logger.info("All camera ingestion threads and workers stopped gracefully.")


# FastAPI Application Definition
app = FastAPI(
    title="CCTV Smart Attendance System API",
    description="Automated classroom student attendance platform using SCRFD, MiniFASNet, ArcFace pgvector, and Centroid tracking.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure Cross-Origin Resource Sharing (CORS) for React 18 frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local hackathon network deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Sub-Routers
app.include_router(students_router, prefix="/api/students", tags=["Students"])
app.include_router(classrooms_router, tags=["Classrooms"])
app.include_router(periods_router, tags=["Periods & Timetable"])
app.include_router(attendance_router, tags=["Attendance & Live Dashboard"])
app.include_router(reports_router, tags=["Excel Reports & Analytics"])


@app.get("/health")
def health_check():
    """System health check endpoint for monitoring."""
    active_cams = camera_manager.get_active_camera_count()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_cameras": active_cams,
        "database": "connected"
    }


@app.get("/api/classrooms/{classroom_id}/snapshot")
def get_classroom_snapshot(classroom_id: int):
    """
    Captures a single high-resolution JPEG snapshot from the classroom camera stream.
    Used by the multi-angle face enrollment wizard.
    """
    stream = camera_manager._streams.get(classroom_id)
    if not stream or not stream.is_running:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera for Classroom #{classroom_id} is not connected or offline."
        )

    frame_data = stream.get_latest_frame()
    if frame_data is None or frame_data.frame is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No frame currently available from Classroom #{classroom_id} camera."
        )

    ret, encoded_jpeg = cv2.imencode(".jpg", frame_data.frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encode camera snapshot."
        )

    from fastapi.responses import Response
    return Response(content=encoded_jpeg.tobytes(), media_type="image/jpeg")


@app.get("/api/classrooms/{classroom_id}/video-feed")
async def get_classroom_video_feed(classroom_id: int):
    """
    Streams low-latency live MJPEG video from the selected classroom camera to the browser.
    """
    stream = camera_manager._streams.get(classroom_id)
    if not stream:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom #{classroom_id} camera stream not found."
        )

    async def mjpeg_generator():
        while True:
            frame_data = stream.get_latest_frame()
            if frame_data is not None and frame_data.frame is not None:
                ret, jpeg = cv2.imencode('.jpg', frame_data.frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n'
                    )
            await asyncio.sleep(0.08)  # ~12 FPS video stream preview

    return StreamingResponse(
        mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws/classrooms/{classroom_id}")
async def websocket_classroom_endpoint(websocket: WebSocket, classroom_id: int):
    """
    WebSocket endpoint providing sub-50ms live attendance, recognition events,
    and anti-spoofing alert pushes directly to the React dashboard.
    """
    await ws_manager.connect(websocket, classroom_id)
    try:
        while True:
            # Keep-alive ping/pong receiver
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, classroom_id)
    except Exception as exc:
        logger.warning(f"[WS] Exception on Classroom #{classroom_id} connection: {exc}")
        ws_manager.disconnect(websocket, classroom_id)
