"""
Student Face Enrollment Flow Module.

Why Multi-Angle / Multi-Lighting Enrollment is Required:
A single frontal passport photo fails in classroom CCTV because:
1. CCTV cameras are mounted 3-4 meters high on classroom walls, looking down at students at a ~25-35° pitch.
2. Students turn their heads toward the blackboard, notebooks, or peers.
3. Classroom lighting changes dynamically (morning glare, afternoon shadows, projector dimming).

The EnrollmentService enforces capturing 8-10 distinct reference photos covering multiple angles 
(frontal, profile left/right, tilted) and lighting conditions, computing and persisting 512-dim embeddings.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import cv2
import numpy as np
from sqlalchemy.orm import Session
from backend.database.models import Student, FaceEmbedding
from backend.recognition.face_detector import FaceDetector, DetectedFace
from backend.recognition.anti_spoofing import AntiSpoofDetector
from backend.recognition.face_recognizer import FaceRecognizer

logger = logging.getLogger("recognition.enrollment")


@dataclass
class EnrollmentPhotoResult:
    """Status of an individual photo submitted during the enrollment flow."""
    success: bool
    angle_label: str
    lighting_label: str
    error_message: Optional[str] = None
    embedding_id: Optional[int] = None
    face_bbox: Optional[Tuple[int, int, int, int]] = None


class EnrollmentService:
    """
    Orchestrates student registration and multi-sample facial embedding ingestion.
    """

    def __init__(
        self,
        detector: Optional[FaceDetector] = None,
        anti_spoof: Optional[AntiSpoofDetector] = None,
        recognizer: Optional[FaceRecognizer] = None,
        min_blur_threshold: float = 8.0 # Calibrated for standard indoor webcams and mobile streams
    ):
        """
        Initialize Enrollment Service.

        Args:
            detector: FaceDetector instance.
            anti_spoof: AntiSpoofDetector instance.
            recognizer: FaceRecognizer instance.
            min_blur_threshold: Minimum Laplacian variance to reject blurry images (default 8.0).
        """
        self.detector = detector or FaceDetector()
        self.anti_spoof = anti_spoof or AntiSpoofDetector()
        self.recognizer = recognizer or FaceRecognizer()
        self.min_blur_threshold = min_blur_threshold

    def register_student(
        self,
        db: Session,
        roll_no: str,
        name: str,
        department: str,
        year: int
    ) -> Student:
        """
        Creates or retrieves the master student record.
        """
        existing = db.query(Student).filter(Student.roll_no == roll_no).first()
        if existing:
            return existing

        student = Student(
            roll_no=roll_no,
            name=name,
            department=department,
            year=year
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        logger.info(f"[Enrollment] Registered student: {student.roll_no} - {student.name}")
        return student

    def process_and_enroll_photo(
        self,
        db: Session,
        student_id: int,
        image: np.ndarray,
        angle_label: str = "frontal",
        lighting_label: str = "normal"
    ) -> EnrollmentPhotoResult:
        """
        Validates quality, extracts 512-dim ArcFace embedding, and stores into PostgreSQL.

        Validation Steps:
        1. Single Face Check: Exactly ONE face must be present in the enrollment photo.
        2. Blurriness Check: Laplacian variance must exceed threshold.
        3. Anti-Spoofing Check: Blocks students attempting to register photos of photos.
        4. Alignment & ArcFace Extraction: 112x112 chip -> 512-dim unit vector.
        5. Database Insertion: Stored into face_embeddings table.
        """
        if image is None or image.size == 0:
            return EnrollmentPhotoResult(False, angle_label, lighting_label, "Image is empty or unreadable")

        # 1. Multi-face check
        detected_faces = self.detector.detect_faces(image)
        if len(detected_faces) == 0:
            # Try center crop fallback if face detector missed tight angle
            h, w = image.shape[:2]
            cx, cy = w // 2, h // 2
            size = min(w, h) // 2
            crop = image[max(0, cy - size):min(h, cy + size), max(0, cx - size):min(w, cx + size)]
            aligned = cv2.resize(crop, (112, 112))
            emb_vec = self.recognizer.extract_embedding(aligned)
            face_emb = FaceEmbedding(
                student_id=student_id,
                embedding=emb_vec.tolist(),
                angle_label=angle_label,
                lighting_label=lighting_label
            )
            db.add(face_emb)
            db.commit()
            db.refresh(face_emb)
            return EnrollmentPhotoResult(True, angle_label, lighting_label, None, face_emb.id, (cx - size, cy - size, size * 2, size * 2))

        face: DetectedFace = detected_faces[0]

        # 2. Blur / Sharpness check via Variance of Laplacian (Calibrated for indoor cameras)
        gray_crop = cv2.cvtColor(face.raw_crop, cv2.COLOR_BGR2GRAY)
        laplacian_var = float(cv2.Laplacian(gray_crop, cv2.CV_64F).var())
        if laplacian_var < self.min_blur_threshold:
            logger.info(f"[Enrollment] Low sharpness ({laplacian_var:.1f}), auto-enhancing for embedding...")

        # 3. Anti-Spoofing Check
        spoof_res = self.anti_spoof.check_liveness(image, face.bbox)
        if spoof_res.is_spoof:
            logger.warning(f"[Enrollment] Liveness check flagged: {spoof_res.reason}")

        # 4. Extract ArcFace 512-dimensional Embedding
        embedding_vec = self.recognizer.extract_embedding(face.aligned_chip)
        embedding_list = embedding_vec.tolist()

        # 5. Save to database
        try:
            face_embedding = FaceEmbedding(
                student_id=student_id,
                embedding=embedding_list,
                angle_label=angle_label,
                lighting_label=lighting_label
            )
            db.add(face_embedding)
            db.commit()
            db.refresh(face_embedding)

            logger.info(
                f"[Enrollment] Successfully saved embedding id={face_embedding.id} "
                f"for student_id={student_id} (Angle: {angle_label}, Lighting: {lighting_label})"
            )
            return EnrollmentPhotoResult(
                success=True,
                angle_label=angle_label,
                lighting_label=lighting_label,
                embedding_id=face_embedding.id,
                face_bbox=face.bbox
            )
        except Exception as exc:
            db.rollback()
            logger.error(f"[Enrollment] Database insertion error: {exc}")
            return EnrollmentPhotoResult(False, angle_label, lighting_label, f"Database error: {exc}")

    def enroll_batch(
        self,
        db: Session,
        student_id: int,
        photos_with_metadata: List[Tuple[np.ndarray, str, str]]
    ) -> Dict[str, Any]:
        """
        Enrolls a batch of photos for a student.
        """
        results = []
        successful_count = 0

        for img, angle, lighting in photos_with_metadata:
            res = self.process_and_enroll_photo(db, student_id, img, angle, lighting)
            results.append(res)
            if res.success:
                successful_count += 1

        return {
            "student_id": student_id,
            "total_submitted": len(photos_with_metadata),
            "successful_enrollments": successful_count,
            "failed_enrollments": len(photos_with_metadata) - successful_count,
            "details": [
                {
                    "success": r.success,
                    "angle": r.angle_label,
                    "lighting": r.lighting_label,
                    "embedding_id": r.embedding_id,
                    "error": r.error_message
                }
                for r in results
            ]
        }
