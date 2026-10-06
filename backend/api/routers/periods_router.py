"""
Academic Period & Timetable Management API Router.

Endpoints:
- GET  /api/periods                    : List periods (filter by date, classroom, teacher)
- POST /api/periods                    : Create new lecture period slot
- GET  /api/periods/{id}               : Get specific period details
- GET  /api/classrooms/{id}/active-period : Get the period currently active in a classroom
- POST /api/periods/{id}/finalize      : Mark remaining unmarked students as absent
"""

import logging
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.database.connection import get_db
from backend.database.models import Period, Classroom, Teacher
from backend.api.schemas import PeriodCreate, PeriodOut
from backend.attendance.period_service import PeriodService

logger = logging.getLogger("api.periods")
router = APIRouter(tags=["Periods & Timetable"])


@router.get("/api/periods", response_model=List[PeriodOut])
def list_periods(
    period_date: Optional[date] = None,
    classroom_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Lists scheduled periods filtered by date, classroom, or teacher."""
    query = db.query(Period)
    if period_date:
        query = query.filter(Period.period_date == period_date)
    if classroom_id:
        query = query.filter(Period.classroom_id == classroom_id)
    if teacher_id:
        query = query.filter(Period.teacher_id == teacher_id)

    periods = query.order_by(Period.period_date.desc(), Period.start_time.asc()).all()
    results = []
    for p in periods:
        p_out = PeriodOut.from_orm(p)
        p_out.classroom_name = p.classroom.name if p.classroom else None
        p_out.teacher_name = p.teacher.name if p.teacher else None
        results.append(p_out)
    return results


@router.post("/api/periods", response_model=PeriodOut, status_code=status.HTTP_201_CREATED)
def create_period(payload: PeriodCreate, db: Session = Depends(get_db)):
    """Creates a new period and initializes the default student attendance roster."""
    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time must be after start time."
        )

    period = Period(
        classroom_id=payload.classroom_id,
        teacher_id=payload.teacher_id,
        subject=payload.subject,
        period_date=payload.period_date,
        start_time=payload.start_time,
        end_time=payload.end_time
    )
    db.add(period)
    db.commit()
    db.refresh(period)

    # Initialize roster
    PeriodService.initialize_period_roster(db, period.id)

    p_out = PeriodOut.from_orm(period)
    p_out.classroom_name = period.classroom.name if period.classroom else None
    p_out.teacher_name = period.teacher.name if period.teacher else None
    return p_out


@router.get("/api/classrooms/{classroom_id}/active-period", response_model=Optional[PeriodOut])
def get_active_period_for_classroom(classroom_id: int, db: Session = Depends(get_db)):
    """
    Returns the period currently running in the classroom right now based on system time.
    """
    active_period = PeriodService.get_active_period(db, classroom_id, datetime.now())
    if not active_period:
        return None

    p_out = PeriodOut.from_orm(active_period)
    p_out.classroom_name = active_period.classroom.name if active_period.classroom else None
    p_out.teacher_name = active_period.teacher.name if active_period.teacher else None
    return p_out


@router.post("/api/periods/{period_id}/finalize")
def finalize_period(period_id: int, db: Session = Depends(get_db)):
    """
    Finalizes an ended period by marking all remaining 'unmarked' students as 'absent'.
    """
    period = db.query(Period).filter(Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found.")

    absent_count = PeriodService.finalize_period_attendance(db, period_id)
    return {
        "message": f"Period {period_id} finalized successfully.",
        "unmarked_converted_to_absent": absent_count
    }
