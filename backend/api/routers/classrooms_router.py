"""
Classrooms & Camera Stream Management API Router.

Endpoints:
- GET   /api/classrooms                     : List all classrooms
- POST  /api/classrooms                     : Register a new classroom with CCTV RTSP URL
- GET   /api/classrooms/{id}                : Get classroom details
- PATCH /api/classrooms/{id}/camera-source  : Switch camera feed to Webcam ("0", "1") or iVCam/RTSP stream URL
- GET   /api/classrooms/{id}/video-feed     : Live MJPEG video stream with face recognition bounding boxes
- GET   /api/classrooms/{id}/snapshot       : Grab single high-res JPEG snapshot from active camera stream
- GET   /api/cameras/status                 : Live health telemetry of all CCTV camera stream workers
"""

import time
import logging
from typing import List, Dict, Any, Optional
import cv2
import numpy as np
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database.connection import get_db, SessionLocal
from backend.database.models import Classroom, Period
from backend.api.schemas import ClassroomCreate, ClassroomOut

logger = logging.getLogger("api.classrooms")
router = APIRouter(tags=["Classrooms & Cameras"])


class CameraSourceUpdate(BaseModel):
    camera_rtsp_url: str # e.g. "0" for webcam / iVCam, or "rtsp://192.168.1.50:554/live"


@router.get("/api/classrooms", response_model=List[ClassroomOut])
def list_classrooms(db: Session = Depends(get_db)):
    """Retrieves all registered classrooms and camera RTSP stream endpoints."""
    return db.query(Classroom).order_by(Classroom.id.asc()).all()


@router.post("/api/classrooms", response_model=ClassroomOut, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomCreate, db: Session = Depends(get_db)):
    """Registers a new classroom with its primary RTSP camera feed."""
    existing = db.query(Classroom).filter(Classroom.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Classroom '{payload.name}' already exists.")

    classroom = Classroom(
        name=payload.name,
        camera_rtsp_url=payload.camera_rtsp_url,
        location=payload.location
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.get("/api/classrooms/{classroom_id}", response_model=ClassroomOut)
def get_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """Retrieves details of a single classroom."""
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found.")
    return classroom


@router.patch("/api/classrooms/{classroom_id}/camera-source", response_model=ClassroomOut)
def update_camera_source(classroom_id: int, payload: CameraSourceUpdate, db: Session = Depends(get_db)):
    """
    Updates the camera source for a classroom (e.g., switches between Webcam '0', iVCam '1', or RTSP URL).
    """
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found.")

    classroom.camera_rtsp_url = payload.camera_rtsp_url.strip()
    db.commit()
    db.refresh(classroom)

    # Dynamically re-register and restart camera stream in CameraManager
    from backend.api.main import camera_manager
    try:
        camera_manager.register_camera(classroom_id=classroom.id, camera_url=classroom.camera_rtsp_url)
        camera_manager.start_camera(classroom_id=classroom.id)
        logger.info(f"[Camera] Switched classroom {classroom_id} feed to: {classroom.camera_rtsp_url}")
    except Exception as exc:
        logger.warning(f"[Camera] Failed to restart stream: {exc}")

    return classroom


@router.get("/api/classrooms/{classroom_id}/snapshot")
def get_camera_snapshot(classroom_id: int, db: Session = Depends(get_db)):
    """
    Captures a single clean snapshot directly from the active camera worker stream.
    Used for enrollment and instant face capture without browser device lock conflicts.
    """
    from backend.api.main import camera_manager
    stream = camera_manager._streams.get(classroom_id)
    frame_data = stream.get_latest_frame() if stream else None

    if frame_data is None or frame_data.frame is None:
        # Fallback to direct read
        classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
        url = classroom.camera_rtsp_url if classroom else "0"
        src = int(url) if url.isdigit() else url
        cap = cv2.VideoCapture(src)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise HTTPException(status_code=400, detail="Camera feed unavailable. Ensure camera is active.")
    else:
        frame = frame_data.frame

    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return Response(content=buffer.tobytes(), media_type="image/jpeg")


def generate_mjpeg_stream(classroom_id: int):
    """
    Generator yielding live JPEG frames from CameraManager's thread-safe buffer with AI overlays.
    """
    from backend.api.main import camera_manager, recognition_pipeline
    db = SessionLocal()

    try:
        while True:
            stream = camera_manager._streams.get(classroom_id)
            frame_data = stream.get_latest_frame() if stream else None

            if frame_data is None or frame_data.frame is None:
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                img[:] = (25, 25, 25)
                cv2.putText(img, f"Classroom #{classroom_id} CCTV Stream", (50, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(img, "Waiting for video frames...", (50, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)
                cv2.putText(img, time.strftime("%H:%M:%S"), (50, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1)
                _, buffer = cv2.imencode('.jpg', img)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.3)
                continue

            frame = frame_data.frame.copy()

            try:
                frame_result = recognition_pipeline.process_frame(db, frame_data)
                for rec in frame_result.recognitions:
                    x = rec.bbox["x"]
                    y = rec.bbox["y"]
                    w = rec.bbox["w"]
                    h = rec.bbox["h"]

                    if rec.is_spoof:
                        color = (0, 0, 255)
                        label = "SPOOF ATTACK BLOCKED"
                    elif rec.status_tier == "confirmed":
                        color = (0, 220, 100)
                        label = f"{rec.match_result.name} ({(rec.confidence_score*100):.0f}%)"
                    elif rec.status_tier == "needs_review":
                        color = (0, 180, 255)
                        label = f"? {rec.match_result.name} ({(rec.confidence_score*100):.0f}%)"
                    else:
                        color = (200, 200, 200)
                        label = "Unknown Face"

                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.rectangle(frame, (x, y - 24), (x + w, y), color, -1)
                    cv2.putText(frame, label, (x + 4, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

            except Exception:
                pass

            cv2.putText(frame, f"CCTV AI Feed - {time.strftime('%Y-%m-%d %H:%M:%S')}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.1)

    finally:
        db.close()


@router.get("/api/classrooms/{classroom_id}/video-feed")
def get_classroom_video_feed(classroom_id: int):
    """
    Streams real-time MJPEG video for a specific classroom with live AI face bounding box overlays.
    """
    return StreamingResponse(
        generate_mjpeg_stream(classroom_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
