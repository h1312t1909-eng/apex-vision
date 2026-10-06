"""
Pydantic Validation Schemas for FastAPI Endpoints.

Provides strongly-typed request and response data contracts for:
- Student registration & enrollment
- Classroom & RTSP camera feeds
- Faculty & Period timetables
- Real-time Attendance records & teacher overrides
- WebSocket live push payloads
"""

from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# ------------------------------------------------------------------------------
# Student Schemas
# ------------------------------------------------------------------------------
class StudentBase(BaseModel):
    roll_no: str = Field(..., description="Unique college roll number (e.g., '2026CS101')")
    name: str = Field(..., description="Full name of student")
    department: str = Field(..., description="Academic department (e.g., 'Computer Science')")
    year: int = Field(..., ge=1, le=5, description="Year of study (1-5)")


class StudentCreate(StudentBase):
    pass


class FaceEmbeddingOut(BaseModel):
    id: int
    angle_label: str
    lighting_label: str
    captured_at: datetime

    class Config:
        from_attributes = True


class StudentOut(StudentBase):
    id: int
    created_at: datetime
    embedding_count: Optional[int] = 0

    class Config:
        from_attributes = True


class EnrollmentResponse(BaseModel):
    student_id: int
    total_submitted: int
    successful_enrollments: int
    failed_enrollments: int
    details: List[Dict[str, Any]]


# ------------------------------------------------------------------------------
# Teacher & Classroom Schemas
# ------------------------------------------------------------------------------
class TeacherOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    department: str

    class Config:
        from_attributes = True


class ClassroomBase(BaseModel):
    name: str = Field(..., description="Classroom name/number (e.g., 'LH-101')")
    camera_rtsp_url: str = Field(..., description="RTSP URL or webcam index ('0')")
    location: Optional[str] = Field(None, description="Physical location")


class ClassroomCreate(ClassroomBase):
    pass


class ClassroomOut(ClassroomBase):
    id: int

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Period & Timetable Schemas
# ------------------------------------------------------------------------------
class PeriodCreate(BaseModel):
    classroom_id: int
    teacher_id: int
    subject: str
    period_date: date
    start_time: time
    end_time: time


class PeriodOut(BaseModel):
    id: int
    classroom_id: int
    teacher_id: int
    subject: str
    period_date: date
    start_time: time
    end_time: time
    classroom_name: Optional[str] = None
    teacher_name: Optional[str] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Attendance & Override Schemas
# ------------------------------------------------------------------------------
class AttendanceRecordOut(BaseModel):
    id: int
    student_id: int
    roll_no: str
    student_name: str
    department: str
    period_id: int
    status: str # 'confirmed', 'needs_review', 'unmarked', 'absent'
    confidence_score: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    marked_by: str # 'system' or 'teacher'
    updated_at: datetime

    class Config:
        from_attributes = True


class TeacherOverrideRequest(BaseModel):
    teacher_id: int = Field(..., description="ID of faculty member making override")
    new_status: str = Field(..., description="New status: 'confirmed', 'needs_review', 'unmarked', or 'absent'")
    reason: str = Field(..., min_length=3, description="Compulsory justification explanation")


class TeacherOverrideOut(BaseModel):
    id: int
    attendance_record_id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    previous_status: str
    new_status: str
    reason: str
    overridden_at: datetime

    class Config:
        from_attributes = True


class RecognitionEventOut(BaseModel):
    id: int
    period_id: int
    classroom_id: int
    student_id: Optional[int]
    student_name: Optional[str] = None
    roll_no: Optional[str] = None
    confidence_score: float
    is_spoof_flagged: bool
    bounding_box: Dict[str, int]
    frame_timestamp: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Live Dashboard & WebSocket Schemas
# ------------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_enrolled: int
    confirmed_count: int
    needs_review_count: int
    unmarked_count: int
    absent_count: int
    spoof_attempts_blocked: int


class WebSocketBroadcastMessage(BaseModel):
    event_type: str # 'recognition', 'attendance_update', 'spoof_alert', 'camera_status'
    classroom_id: int
    period_id: Optional[int]
    timestamp: datetime
    data: Dict[str, Any]
