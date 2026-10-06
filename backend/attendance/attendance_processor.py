"""
Attendance Processor & Teacher Override Module.

Coordinates recognition outputs, tracking state, deduplication, and database persistence.
Enforces the 4 confidence-tiered attendance states:
1. 'confirmed'    : High confidence (score >= 0.68) ArcFace match without spoof flags.
2. 'needs_review' : Marginal confidence (0.50 <= score < 0.68) requiring faculty check.
3. 'unmarked'     : Default waiting state during an active lecture period.
4. 'absent'       : No conclusive recognition event before period conclusion.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.database.models import (
    Period, Student, AttendanceRecord, TeacherOverride, RecognitionEvent
)
from backend.recognition.pipeline import FrameRecognitionResult, SingleFaceRecognition
from backend.attendance.tracker import CentroidTracker, TrackedFace
from backend.attendance.dedup import AttendanceDeduplicator
from backend.attendance.period_service import PeriodService

logger = logging.getLogger("attendance.processor")


class AttendanceProcessor:
    """
    Main business logic engine translating continuous computer vision detections into 
    clean, auditable academic attendance records.
    """

    def __init__(
        self,
        deduplicator: Optional[AttendanceDeduplicator] = None
    ):
        """
        Initialize Attendance Processor.
        """
        self.deduplicator = deduplicator or AttendanceDeduplicator()
        # Per-classroom centroid trackers: classroom_id -> CentroidTracker
        self._trackers: Dict[int, CentroidTracker] = {}

    def _get_tracker(self, classroom_id: int) -> CentroidTracker:
        """Retrieves or instantiates a CentroidTracker for a classroom."""
        if classroom_id not in self._trackers:
            self._trackers[classroom_id] = CentroidTracker(max_disappeared=15, max_distance=120.0)
        return self._trackers[classroom_id]

    def process_frame_recognition(
        self,
        db: Session,
        frame_result: FrameRecognitionResult,
        override_period_id: Optional[int] = None
    ) -> List[AttendanceRecord]:
        """
        Processes a single frame's recognition outcomes:
        1. Checks active period boundary.
        2. Updates centroid tracker with detected bounding boxes.
        3. Persists raw RecognitionEvent records for forensic auditing.
        4. Applies Redis dedup before updating clean AttendanceRecord derived states.
        5. Updates entry_time on first detection, and exit_time on ongoing detections.

        Args:
            db: Database session.
            frame_result: FrameRecognitionResult from Stage 3.
            override_period_id: Optional forced period ID for testing/simulations.

        Returns:
            List of updated AttendanceRecord objects.
        """
        classroom_id = frame_result.classroom_id
        timestamp = frame_result.frame_timestamp
        
        # 1. Resolve active period boundary
        period = None
        if override_period_id is not None:
            period = db.query(Period).filter(Period.id == override_period_id).first()
        else:
            period = PeriodService.get_active_period(db, classroom_id, timestamp)

        # If no scheduled lecture is active in this classroom right now, skip attendance updates
        if not period:
            return []

        # 2. Update Centroid Tracker for entry/exit tracking
        tracker = self._get_tracker(classroom_id)
        bboxes = [
            (r.bbox["x"], r.bbox["y"], r.bbox["w"], r.bbox["h"])
            for r in frame_result.recognitions
        ]
        active_tracks, deregistered_tracks = tracker.update(bboxes, timestamp)

        # 3. Persist raw recognition events (Forensic audit trail)
        if frame_result.raw_events:
            for event in frame_result.raw_events:
                event.period_id = period.id
                db.add(event)
            db.flush()

        # 4. Process matched students and update attendance records
        updated_records: List[AttendanceRecord] = []

        for rec in frame_result.recognitions:
            # Skip unidentified faces or blocked spoof attacks
            if rec.student_id is None or rec.is_spoof:
                continue

            # Check deduplication cache to prevent hammering DB on every 500ms frame
            should_write = self.deduplicator.should_process_attendance(
                period_id=period.id,
                student_id=rec.student_id,
                new_status=rec.status_tier,
                new_confidence=rec.confidence_score
            )

            # Query existing attendance record for (student_id, period_id)
            att_record = db.query(AttendanceRecord).filter(
                and_(
                    AttendanceRecord.period_id == period.id,
                    AttendanceRecord.student_id == rec.student_id
                )
            ).first()

            if not att_record:
                # First time creating record for this student in this period
                att_record = AttendanceRecord(
                    student_id=rec.student_id,
                    period_id=period.id,
                    status=rec.status_tier,
                    confidence_score=rec.confidence_score,
                    entry_time=timestamp, # Entry timestamp
                    exit_time=timestamp,  # Initial exit timestamp is same as entry
                    marked_by="system"
                )
                db.add(att_record)
                updated_records.append(att_record)
            else:
                # Existing record: update exit timestamp continuously
                att_record.exit_time = timestamp
                
                # Upgrade status if confidence tier improved (e.g., needs_review -> confirmed)
                if should_write:
                    if att_record.status != "confirmed" and rec.status_tier == "confirmed":
                        att_record.status = "confirmed"
                    elif att_record.status == "unmarked":
                        att_record.status = rec.status_tier

                    if rec.confidence_score > (att_record.confidence_score or 0.0):
                        att_record.confidence_score = rec.confidence_score

                    att_record.updated_at = datetime.utcnow()
                    updated_records.append(att_record)

        # 5. Flush and commit database changes
        db.commit()
        return updated_records

    def apply_teacher_override(
        self,
        db: Session,
        attendance_record_id: int,
        teacher_id: int,
        new_status: str,
        reason: str
    ) -> Tuple[AttendanceRecord, TeacherOverride]:
        """
        Applies a faculty manual status override with compulsory audit logging.

        Args:
            db: Database session.
            attendance_record_id: Target AttendanceRecord ID.
            teacher_id: ID of the teacher authorizing the change.
            new_status: One of ('confirmed', 'needs_review', 'unmarked', 'absent').
            reason: Justification text explaining why manual override was made.

        Returns:
            Tuple of (updated AttendanceRecord, created TeacherOverride audit log).
        """
        valid_statuses = {"confirmed", "needs_review", "unmarked", "absent"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {valid_statuses}")

        if not reason or len(reason.strip()) < 3:
            raise ValueError("A clear justification reason is mandatory for teacher manual overrides.")

        att_record = db.query(AttendanceRecord).filter(AttendanceRecord.id == attendance_record_id).first()
        if not att_record:
            raise ValueError(f"Attendance record with ID {attendance_record_id} not found.")

        previous_status = att_record.status

        # 1. Update attendance record state
        att_record.status = new_status
        att_record.marked_by = "teacher"
        att_record.updated_at = datetime.utcnow()

        # 2. Create immutable audit trail entry
        override_log = TeacherOverride(
            attendance_record_id=attendance_record_id,
            teacher_id=teacher_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason.strip(),
            overridden_at=datetime.utcnow()
        )
        db.add(override_log)

        # 3. Clear Redis deduplication key so subsequent camera passes don't overwrite teacher override
        self.deduplicator.clear_period_cache(att_record.period_id)

        db.commit()
        db.refresh(att_record)
        db.refresh(override_log)

        logger.info(
            f"[Override] Teacher {teacher_id} changed record {attendance_record_id} "
            f"from '{previous_status}' to '{new_status}'. Reason: {reason}"
        )
        return att_record, override_log
