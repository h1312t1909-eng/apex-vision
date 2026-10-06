"""
Attendance & Live Dashboard API Router.

Endpoints:
- GET  /api/periods/{id}/attendance          : Live student attendance roster for period
- GET  /api/periods/{id}/stats               : Overview metrics for period (confirmed, review, absent, spoofs)
- POST /api/attendance/{record_id}/override  : Teacher manual override with reason & audit trail
- GET  /api/attendance/{record_id}/overrides : View audit history for an attendance record
- GET  /api/periods/{id}/events              : View append-only raw recognition events log
- POST /api/periods/{id}/scan-now            : Instant one-click camera frame capture & recognition scan
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.database.connection import get_db
from backend.database.models import (
    Period, Student, AttendanceRecord, TeacherOverride, RecognitionEvent, Teacher
)
from backend.api.schemas import (
    AttendanceRecordOut, TeacherOverrideRequest, TeacherOverrideOut, 
    RecognitionEventOut, DashboardStats
)
from backend.attendance.attendance_processor import AttendanceProcessor
from backend.api.websocket_manager import ws_manager

logger = logging.getLogger("api.attendance")
router = APIRouter(tags=["Attendance & Live Dashboard"])
attendance_processor = AttendanceProcessor()


@router.get("/api/periods/{period_id}/attendance", response_model=List[AttendanceRecordOut])
def get_period_attendance(period_id: int, db: Session = Depends(get_db)):
    """
    Returns the complete student attendance roster for a specific period.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")

    records = db.query(AttendanceRecord).filter(AttendanceRecord.period_id == period_id).all()
    results = []
    for r in records:
        results.append(
            AttendanceRecordOut(
                id=r.id,
                student_id=r.student_id,
                roll_no=r.student.roll_no if r.student else "UNKNOWN",
                student_name=r.student.name if r.student else "UNKNOWN",
                department=r.student.department if r.student else "UNKNOWN",
                period_id=r.period_id,
                status=r.status,
                confidence_score=r.confidence_score,
                entry_time=r.entry_time,
                exit_time=r.exit_time,
                marked_by=r.marked_by,
                updated_at=r.updated_at
            )
        )
    return results


@router.get("/api/periods/{period_id}/stats", response_model=DashboardStats)
def get_period_stats(period_id: int, db: Session = Depends(get_db)):
    """
    Calculates aggregated attendance metrics and spoof alerts for the live dashboard cards.
    """
    records = db.query(AttendanceRecord).filter(AttendanceRecord.period_id == period_id).all()
    spoof_count = db.query(RecognitionEvent).filter(
        and_(RecognitionEvent.period_id == period_id, RecognitionEvent.is_spoof_flagged == True)
    ).count()

    total = len(records)
    confirmed = sum(1 for r in records if r.status == "confirmed")
    needs_review = sum(1 for r in records if r.status == "needs_review")
    unmarked = sum(1 for r in records if r.status == "unmarked")
    absent = sum(1 for r in records if r.status == "absent")

    return DashboardStats(
        total_enrolled=total,
        confirmed_count=confirmed,
        needs_review_count=needs_review,
        unmarked_count=unmarked,
        absent_count=absent,
        spoof_attempts_blocked=spoof_count
    )


@router.post("/api/attendance/{record_id}/override", response_model=AttendanceRecordOut)
async def teacher_override_attendance(
    record_id: int,
    payload: TeacherOverrideRequest,
    db: Session = Depends(get_db)
):
    """
    Allows faculty to manually update a student's attendance with compulsory justification audit logging.
    """
    teacher = db.query(Teacher).filter(Teacher.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found.")

    try:
        att_record, override_log = attendance_processor.apply_teacher_override(
            db=db,
            attendance_record_id=record_id,
            teacher_id=payload.teacher_id,
            new_status=payload.new_status,
            reason=payload.reason
        )

        # Broadcast live update to React dashboard via WebSocket
        await ws_manager.broadcast_to_classroom(
            classroom_id=att_record.period.classroom_id,
            message={
                "event_type": "attendance_update",
                "classroom_id": att_record.period.classroom_id,
                "period_id": att_record.period_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "record_id": att_record.id,
                    "student_id": att_record.student_id,
                    "student_name": att_record.student.name if att_record.student else "",
                    "roll_no": att_record.student.roll_no if att_record.student else "",
                    "status": att_record.status,
                    "marked_by": "teacher",
                    "override_reason": payload.reason
                }
            }
        )

        return AttendanceRecordOut(
            id=att_record.id,
            student_id=att_record.student_id,
            roll_no=att_record.student.roll_no if att_record.student else "UNKNOWN",
            student_name=att_record.student.name if att_record.student else "UNKNOWN",
            department=att_record.student.department if att_record.student else "UNKNOWN",
            period_id=att_record.period_id,
            status=att_record.status,
            confidence_score=att_record.confidence_score,
            entry_time=att_record.entry_time,
            exit_time=att_record.exit_time,
            marked_by=att_record.marked_by,
            updated_at=att_record.updated_at
        )

    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))


@router.get("/api/attendance/{record_id}/overrides", response_model=List[TeacherOverrideOut])
def get_attendance_overrides(record_id: int, db: Session = Depends(get_db)):
    """
    Returns full immutable audit trail for an attendance record.
    """
    overrides = db.query(TeacherOverride).filter(TeacherOverride.attendance_record_id == record_id).order_by(TeacherOverride.overridden_at.desc()).all()
    results = []
    for o in overrides:
        results.append(
            TeacherOverrideOut(
                id=o.id,
                attendance_record_id=o.attendance_record_id,
                teacher_id=o.teacher_id,
                teacher_name=o.teacher.name if o.teacher else "Unknown",
                previous_status=o.previous_status,
                new_status=o.new_status,
                reason=o.reason,
                overridden_at=o.overridden_at
            )
        )
    return results


@router.get("/api/periods/{period_id}/events", response_model=List[RecognitionEventOut])
def get_period_recognition_events(
    period_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Returns recent raw recognition events (append-only forensic audit log).
    """
    events = db.query(RecognitionEvent).filter(
        RecognitionEvent.period_id == period_id
    ).order_by(RecognitionEvent.frame_timestamp.desc()).limit(limit).all()

    results = []
    for e in events:
        results.append(
            RecognitionEventOut(
                id=e.id,
                period_id=e.period_id,
                classroom_id=e.classroom_id,
                student_id=e.student_id,
                student_name=e.student.name if e.student else "Unidentified",
                roll_no=e.student.roll_no if e.student else None,
                confidence_score=e.confidence_score,
                is_spoof_flagged=e.is_spoof_flagged,
                bounding_box=e.bounding_box,
                frame_timestamp=e.frame_timestamp
            )
        )
    return results


@router.post("/api/periods/{period_id}/scan-now")
async def trigger_instant_camera_scan(period_id: int, db: Session = Depends(get_db)):
    """
    Captures the latest camera frame immediately and executes recognition.
    """
    from backend.api.main import camera_manager, recognition_pipeline
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")

    stream = camera_manager._streams.get(period.classroom_id)
    frame_data = stream.get_latest_frame() if stream else None

    if not frame_data:
        # Fallback: grab frame directly
        import cv2
        cap = cv2.VideoCapture(int(period.classroom.camera_rtsp_url) if period.classroom.camera_rtsp_url.isdigit() else period.classroom.camera_rtsp_url)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise HTTPException(status_code=400, detail="Could not read frame from camera. Ensure iVCam/Webcam is active.")
        from backend.camera_ingestion.stream_capture import FrameData
        frame_data = FrameData(
            classroom_id=period.classroom_id,
            camera_url=period.classroom.camera_rtsp_url,
            frame=frame,
            timestamp=datetime.utcnow(),
            frame_number=1
        )

    # Process frame through recognition pipeline
    frame_result = recognition_pipeline.process_frame(db, frame_data, period_id=period.id)
    updated_records = attendance_processor.process_frame_recognition(db, frame_result, override_period_id=period.id)

    # Broadcast updates via WebSocket
    for att in updated_records:
        await ws_manager.broadcast_to_classroom(
            period.classroom_id,
            {
                "event_type": "attendance_update",
                "classroom_id": period.classroom_id,
                "period_id": att.period_id,
                "timestamp": att.updated_at.isoformat(),
                "data": {
                    "record_id": att.id,
                    "student_id": att.student_id,
                    "student_name": att.student.name if att.student else "",
                    "roll_no": att.student.roll_no if att.student else "",
                    "status": att.status,
                    "confidence_score": att.confidence_score,
                    "entry_time": att.entry_time.isoformat() if att.entry_time else None,
                    "exit_time": att.exit_time.isoformat() if att.exit_time else None,
                    "marked_by": att.marked_by
                }
            }
        )

    return {
        "status": "success",
        "faces_detected": frame_result.faces_detected_count,
        "records_updated": len(updated_records),
        "recognitions": [
            {
                "student_name": r.match_result.name,
                "confidence": r.confidence_score,
                "status": r.status_tier,
                "is_spoof": r.is_spoof
            }
            for r in frame_result.recognitions
        ]
    }
