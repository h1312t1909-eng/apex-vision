"""
Fresh Database Reset & Mock Data Initialization Script.

Cleans all old dynamic events/attendance and seeds clean classrooms, faculty,
and mock students with active timetable periods for today.
"""

from datetime import date, time, datetime
import numpy as np
from sqlalchemy import text
from backend.database.connection import SessionLocal, run_migrations
from backend.database.models import (
    Student, FaceEmbedding, Teacher, Classroom, Period, AttendanceRecord, RecognitionEvent, TeacherOverride
)
from backend.attendance.dedup import AttendanceDeduplicator
from backend.attendance.period_service import PeriodService


def generate_mock_embedding() -> list[float]:
    """Generates 512-dim unit-normalized vector."""
    vec = np.random.randn(512).astype(np.float32)
    norm = np.linalg.norm(vec)
    return (vec / (norm + 1e-7)).tolist()


def reset_fresh_database():
    """
    Cleans all dynamic tables and seeds fresh master classrooms, teachers, and student roster.
    """
    print("[Reset] Running database migrations...")
    run_migrations()

    db = SessionLocal()
    try:
        print("[Reset] Purging recognition events, attendance records, overrides, embeddings, and students...")
        db.query(TeacherOverride).delete()
        db.query(RecognitionEvent).delete()
        db.query(AttendanceRecord).delete()
        db.query(FaceEmbedding).delete()
        db.query(Period).delete()
        db.query(Student).delete()
        db.query(Classroom).delete()
        db.query(Teacher).delete()
        db.commit()

        # Reset sequences
        for seq in ["recognition_events_id_seq", "attendance_records_id_seq", "teacher_overrides_id_seq", 
                    "face_embeddings_id_seq", "students_id_seq", "periods_id_seq", "classrooms_id_seq", "teachers_id_seq"]:
            try:
                db.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH 1;"))
            except Exception:
                pass
        db.commit()

        print("[Reset] Creating master classrooms (Room 1 = Laptop/Default, Room 2 = iVCam/Mobile)...")
        classrooms = [
            Classroom(name="LH-101 (Lecture Hall)", camera_rtsp_url="0", location="Building A, Floor 1"),
            Classroom(name="CS-Lab-1 (AI Vision Lab)", camera_rtsp_url="1", location="Building B, Floor 2"),
        ]
        db.add_all(classrooms)
        db.flush()

        print("[Reset] Creating master faculty...")
        teachers = [
            Teacher(name="Dr. Alan Turing", email="alan.turing@college.edu", department="Computer Science"),
            Teacher(name="Dr. Grace Hopper", email="grace.hopper@college.edu", department="Computer Science"),
        ]
        db.add_all(teachers)
        db.flush()

        print("[Reset] Seeding sample mock students...")
        sample_students = [
            ("2026CS101", "Alex Rivers", "Computer Science", 3),
            ("2026CS102", "Maya Lin", "Computer Science", 3),
            ("2026CS103", "Rohan Verma", "Computer Science", 3),
            ("2026CS104", "Sophia Chen", "Computer Science", 3),
            ("2026CS105", "Liam Patel", "Computer Science", 3),
            ("2026CS106", "Emily Davis", "Computer Science", 3),
        ]

        angles = ["frontal", "profile_left", "profile_right", "tilted_up", "tilted_down"]
        for roll, sname, dept, yr in sample_students:
            st = Student(roll_no=roll, name=sname, department=dept, year=yr)
            db.add(st)
            db.flush()

            # Seed 5 mock embeddings per student
            for ang in angles:
                db.add(FaceEmbedding(
                    student_id=st.id,
                    embedding=generate_mock_embedding(),
                    angle_label=ang,
                    lighting_label="normal"
                ))

        db.flush()

        print("[Reset] Creating fresh active periods for today...")
        today = date.today()
        periods = [
            Period(
                classroom_id=classrooms[0].id,
                teacher_id=teachers[0].id,
                subject="CS401: Computer Vision & Deep Learning",
                period_date=today,
                start_time=time(0, 0, 0),
                end_time=time(23, 59, 59)
            ),
            Period(
                classroom_id=classrooms[1].id,
                teacher_id=teachers[1].id,
                subject="CS402: Distributed Systems & Cloud",
                period_date=today,
                start_time=time(0, 0, 0),
                end_time=time(23, 59, 59)
            )
        ]
        db.add_all(periods)
        db.flush()

        # Initialize student roster for today's periods (all start as unmarked with 0 spoof logs)
        for p in periods:
            PeriodService.initialize_period_roster(db, p.id)

        # Clear Redis deduplication cache
        dedup = AttendanceDeduplicator()
        dedup.clear_period_cache(1)
        dedup.clear_period_cache(2)

        print("[Reset] Database reset and seeded with clean mock students & active timetable slots!")

    except Exception as exc:
        db.rollback()
        print(f"[Reset Error] {exc}")
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    reset_fresh_database()
