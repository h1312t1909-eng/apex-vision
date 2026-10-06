"""
Database Seeder Script.

Why this script exists:
Quickly initializes mock classrooms, faculty, enrolled students with simulated
512-dimensional unit-normalized face embeddings, and active periods so that judges 
and developers can immediately test recognition, WebSocket streaming, and report generation.
"""

from datetime import datetime, date, time
import numpy as np
from sqlalchemy.orm import Session
from backend.database.connection import SessionLocal, run_migrations
from backend.database.models import Student, FaceEmbedding, Teacher, Classroom, Period, AttendanceRecord


def generate_mock_embedding() -> list[float]:
    """
    Generates a 512-dimensional random float vector normalized to unit length (L2 norm = 1.0).
    """
    vec = np.random.randn(512).astype(np.float32)
    norm = np.linalg.norm(vec)
    normalized_vec = (vec / (norm + 1e-7)).tolist()
    return normalized_vec


def seed_database():
    """
    Seeds initial reference data for demo and hackathon presentation.
    """
    print("[Seed] Running database migrations first...")
    run_migrations()

    db: Session = SessionLocal()
    try:
        # Check if classrooms exist and ensure camera_rtsp_url is set to "0" (Webcam/iVCam)
        c1 = db.query(Classroom).filter(Classroom.id == 1).first()
        if c1:
            c1.camera_rtsp_url = "0"
            db.commit()
            print("[Seed] Updated Classroom 1 camera_rtsp_url to '0' (Webcam/iVCam).")

        # 1. Check if database already has seed data
        if db.query(Teacher).first():
            print("[Seed] Database already contains teachers & periods. Skipping full seed.")
            return

        print("[Seed] Inserting sample teachers...")
        teachers = [
            Teacher(name="Dr. Alan Turing", email="alan.turing@college.edu", department="Computer Science"),
            Teacher(name="Dr. Grace Hopper", email="grace.hopper@college.edu", department="Computer Science"),
            Teacher(name="Dr. Claude Shannon", email="claude.shannon@college.edu", department="Electronics & Comm"),
        ]
        db.add_all(teachers)
        db.flush()

        print("[Seed] Inserting sample classrooms with RTSP/Webcam configurations...")
        classrooms = [
            Classroom(name="LH-101 (Lecture Hall)", camera_rtsp_url="0", location="Building A, Floor 1"), # "0" for Webcam/iVCam
            Classroom(name="CS-Lab-1 (AI Vision Lab)", camera_rtsp_url="1", location="Building B, Floor 2"),
        ]
        db.add_all(classrooms)
        db.flush()

        print("[Seed] Inserting enrolled students and face embeddings...")
        sample_students_data = [
            ("2026CS101", "Alex Rivers", "Computer Science", 3),
            ("2026CS102", "Maya Lin", "Computer Science", 3),
            ("2026CS103", "Rohan Verma", "Computer Science", 3),
            ("2026CS104", "Sophia Chen", "Computer Science", 3),
            ("2026CS105", "Liam Patel", "Computer Science", 3),
            ("2026CS106", "Emily Davis", "Computer Science", 3),
            ("2026CS107", "Noah Kumar", "Computer Science", 3),
            ("2026CS108", "Zara Ahmed", "Computer Science", 3),
        ]

        angles = ["frontal", "profile_left_30", "profile_right_30", "tilted_up", "tilted_down"]
        lighting_conditions = ["normal_daylight", "indoor_tube_light", "low_ambient"]

        for roll_no, name, dept, year in sample_students_data:
            student = Student(roll_no=roll_no, name=name, department=dept, year=year)
            db.add(student)
            db.flush()

            # Seed 5-8 face embeddings per student to simulate multi-angle enrollment
            for i in range(6):
                angle = angles[i % len(angles)]
                lighting = lighting_conditions[i % len(lighting_conditions)]
                emb_vec = generate_mock_embedding()
                
                face_emb = FaceEmbedding(
                    student_id=student.id,
                    embedding=emb_vec,
                    angle_label=angle,
                    lighting_label=lighting
                )
                db.add(face_emb)

        db.flush()

        print("[Seed] Inserting active timetable periods for today...")
        today = date.today()
        periods = [
            Period(
                classroom_id=classrooms[0].id,
                teacher_id=teachers[0].id,
                subject="CS401: Computer Vision & Deep Learning",
                period_date=today,
                start_time=time(0, 0, 0),
                end_time=time(23, 59, 59) # 24-hour window so it's always actively running for live demo
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

        db.commit()
        print("[Seed] Database successfully seeded with classrooms, teachers, students, embeddings, and periods!")

    except Exception as exc:
        db.rollback()
        print(f"[Seed Error] Failed to seed database: {exc}")
        raise exc
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
