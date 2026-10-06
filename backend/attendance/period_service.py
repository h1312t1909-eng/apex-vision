"""
Academic Period Boundary & Timetable Lifecycle Service.

Why Period Boundary Logic is Mandatory:
CCTV cameras run 24/7. However, university attendance rules state:
1. Student presence in Classroom 101 at 08:45 AM must NOT count toward the 09:00-10:00 AM Deep Learning class.
2. A student leaving at 09:10 AM during a 09:00-10:00 AM class has an exit time recorded, 
   enabling minimum dwell-time verification.
3. At the end of a period (10:00 AM), all remaining 'unmarked' students are automatically 
   finalized as 'absent'.
"""

import logging
from datetime import datetime, date, time
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.database.models import Period, Classroom, Student, AttendanceRecord

logger = logging.getLogger("attendance.period")


class PeriodService:
    """
    Manages timetable resolution, boundary enforcement, and period lifecycle transitions.
    """

    @staticmethod
    def get_active_period(
        db: Session,
        classroom_id: int,
        current_dt: Optional[datetime] = None
    ) -> Optional[Period]:
        """
        Finds the scheduled period actively running in a classroom at the given timestamp.

        Args:
            db: Database session.
            classroom_id: Database ID of the classroom.
            current_dt: Target datetime (defaults to UTC now).

        Returns:
            Period object if within start_time <= current_time <= end_time, else None.
        """
        now = current_dt or datetime.now()
        target_date = now.date()
        target_time = now.time()

        # Query period matching classroom, date, and bounded time window
        period = db.query(Period).filter(
            and_(
                Period.classroom_id == classroom_id,
                Period.period_date == target_date,
                Period.start_time <= target_time,
                Period.end_time >= target_time
            )
        ).first()

        return period

    @staticmethod
    def initialize_period_roster(db: Session, period_id: int) -> int:
        """
        Pre-populates the attendance_records table with 'unmarked' status for all eligible students.

        Why pre-population:
        Allows the live dashboard to immediately display the complete classroom roster 
        with all students in 'unmarked' or 'absent' state before the teacher even starts roll call.
        """
        period = db.query(Period).filter(Period.id == period_id).first()
        if not period:
            return 0

        # Fetch all students in the database (or scoped by department/year)
        all_students = db.query(Student).all()
        created_count = 0

        for student in all_students:
            # Check if record already exists to satisfy UNIQUE(student_id, period_id)
            existing = db.query(AttendanceRecord).filter(
                and_(
                    AttendanceRecord.period_id == period_id,
                    AttendanceRecord.student_id == student.id
                )
            ).first()

            if not existing:
                record = AttendanceRecord(
                    student_id=student.id,
                    period_id=period_id,
                    status="unmarked",
                    confidence_score=0.0,
                    entry_time=None,
                    exit_time=None,
                    marked_by="system"
                )
                db.add(record)
                created_count += 1

        db.commit()
        logger.info(f"[PeriodService] Initialized {created_count} attendance records for period {period_id}")
        return created_count

    @staticmethod
    def finalize_period_attendance(db: Session, period_id: int) -> int:
        """
        Finalizes an ended period by marking any remaining 'unmarked' records as 'absent'.
        """
        unmarked_records = db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.period_id == period_id,
                AttendanceRecord.status == "unmarked"
            )
        ).all()

        for rec in unmarked_records:
            rec.status = "absent"
            rec.updated_at = datetime.utcnow()

        db.commit()
        logger.info(f"[PeriodService] Finalized period {period_id}: {len(unmarked_records)} unmarked set to 'absent'")
        return len(unmarked_records)
