"""
Student Management & Face Enrollment API Router.

Endpoints:
- POST /api/students             : Register a new student
- GET  /api/students             : List all enrolled students with embedding counts
- GET  /api/students/{id}        : Get single student profile & embedding breakdown
- POST /api/students/{id}/enroll : Upload multi-angle/lighting reference photos for ArcFace enrollment
"""

import logging
from typing import List, Optional
from datetime import date
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Student, FaceEmbedding, Period, AttendanceRecord
from backend.api.schemas import StudentCreate, StudentOut, EnrollmentResponse
from backend.recognition.enrollment import EnrollmentService

logger = logging.getLogger("api.students")
router = APIRouter(prefix="/api/students", tags=["Students & Enrollment"])
enrollment_service = EnrollmentService()


@router.post("", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def register_student(payload: StudentCreate, db: Session = Depends(get_db)):
    """
    Registers a new student in the database and ensures they are added to active periods.
    """
    existing = db.query(Student).filter(Student.roll_no == payload.roll_no).first()
    if existing:
        student = existing
    else:
        student = Student(
            roll_no=payload.roll_no,
            name=payload.name,
            department=payload.department,
            year=payload.year
        )
        db.add(student)
        db.commit()
        db.refresh(student)

    # Pre-populate AttendanceRecord in today's periods for instant visibility
    today_periods = db.query(Period).filter(Period.period_date == date.today()).all()
    for p in today_periods:
        att = db.query(AttendanceRecord).filter(
            AttendanceRecord.period_id == p.id,
            AttendanceRecord.student_id == student.id
        ).first()
        if not att:
            new_att = AttendanceRecord(
                student_id=student.id,
                period_id=p.id,
                status="unmarked",
                confidence_score=0.0,
                marked_by="system"
            )
            db.add(new_att)
    db.commit()

    student.embedding_count = len(student.face_embeddings)
    return student


@router.get("", response_model=List[StudentOut])
def list_students(
    department: Optional[str] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves list of registered students with their total enrolled face embedding counts.
    """
    query = db.query(Student)
    if department:
        query = query.filter(Student.department == department)
    if year:
        query = query.filter(Student.year == year)

    students = query.order_by(Student.roll_no.asc()).all()
    for s in students:
        s.embedding_count = len(s.face_embeddings)
    return students


@router.get("/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    """
    Retrieves detailed student profile.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    student.embedding_count = len(student.face_embeddings)
    return student


@router.post("/{student_id}/enroll", response_model=EnrollmentResponse)
async def enroll_student_photos(
    student_id: int,
    photos: List[UploadFile] = File(..., description="8-10 face photos covering multiple angles and lighting"),
    angles: List[str] = Form(..., description="Angle label per photo (e.g., 'frontal', 'profile_left', 'tilted')"),
    lighting: List[str] = Form(..., description="Lighting label per photo (e.g., 'normal', 'low_light')"),
    db: Session = Depends(get_db)
):
    """
    Processes and validates reference photos for ArcFace face embedding extraction.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if len(photos) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No photos uploaded.")

    photos_with_metadata = []
    for idx, photo_file in enumerate(photos):
        file_bytes = await photo_file.read()
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        angle_lbl = angles[idx] if idx < len(angles) else "frontal"
        lighting_lbl = lighting[idx] if idx < len(lighting) else "normal"

        if img is not None:
            photos_with_metadata.append((img, angle_lbl, lighting_lbl))

    # Run batch enrollment through EnrollmentService
    result = enrollment_service.enroll_batch(db, student_id, photos_with_metadata)
    return result
