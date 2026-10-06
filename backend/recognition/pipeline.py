"""
Unified Recognition Pipeline Module.

Coordinates the end-to-end computer vision lifecycle for each sampled CCTV frame:
1. Multi-Face Detection: Discovers all face bounding boxes and 5-point landmarks.
2. Anti-Spoofing Verification: Checks each face for presentation attacks (printed photos, screens).
3. ArcFace Vector Extraction: Generates 512-dim normalized feature embeddings.
4. Database Vector Search: Queries pgvector via HNSW cosine distance index.
5. Audit Event Generation: Constructs raw RecognitionEvent objects for immutable DB logging.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np
from sqlalchemy.orm import Session

from backend.camera_ingestion.stream_capture import FrameData
from backend.recognition.face_detector import FaceDetector, DetectedFace
from backend.recognition.anti_spoofing import AntiSpoofDetector, SpoofCheckResult
from backend.recognition.face_recognizer import FaceRecognizer, MatchResult
from backend.database.models import RecognitionEvent

logger = logging.getLogger("recognition.pipeline")


@dataclass
class SingleFaceRecognition:
    """Detailed recognition outcome for an individual detected face."""
    bbox: Dict[str, int]               # {"x": 100, "y": 150, "w": 60, "h": 70}
    detector_confidence: float
    is_spoof: bool
    liveness_score: float
    match_result: MatchResult
    student_id: Optional[int]
    confidence_score: float
    status_tier: str                   # 'confirmed', 'needs_review', 'unmarked'


@dataclass
class FrameRecognitionResult:
    """Aggregated recognition result for an entire CCTV frame."""
    classroom_id: int
    frame_timestamp: datetime
    frame_number: int
    faces_detected_count: int
    recognitions: List[SingleFaceRecognition]
    raw_events: List[RecognitionEvent]


class RecognitionPipeline:
    """
    High-throughput face detection, anti-spoofing, and recognition inference pipeline.
    """

    def __init__(
        self,
        detector: Optional[FaceDetector] = None,
        anti_spoof: Optional[AntiSpoofDetector] = None,
        recognizer: Optional[FaceRecognizer] = None
    ):
        """
        Initialize the Recognition Pipeline.
        """
        self.detector = detector or FaceDetector()
        self.anti_spoof = anti_spoof or AntiSpoofDetector()
        self.recognizer = recognizer or FaceRecognizer()

    def process_frame(
        self,
        db: Session,
        frame_data: FrameData,
        period_id: Optional[int] = None
    ) -> FrameRecognitionResult:
        """
        Processes a single CCTV frame through the full recognition pipeline.

        Args:
            db: Database session for pgvector similarity lookups.
            frame_data: Captured frame containing image array and timestamp.
            period_id: Current active academic period ID (if applicable).

        Returns:
            FrameRecognitionResult with all detected students, bounding boxes, and audit events.
        """
        frame = frame_data.frame
        ts = frame_data.timestamp
        classroom_id = frame_data.classroom_id

        # 1. Multi-Face Detection (Returns all student faces in the classroom frame)
        detected_faces = self.detector.detect_faces(frame)

        recognitions: List[SingleFaceRecognition] = []
        raw_events: List[RecognitionEvent] = []

        # 2. Iterate through each detected face
        for face in detected_faces:
            x, y, w, h = face.bbox
            bbox_dict = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}

            # 3. Anti-Spoofing Liveness Check
            spoof_res = self.anti_spoof.check_liveness(frame, face.bbox)

            # If spoof attack is detected, block matching and flag immediately
            if spoof_res.is_spoof:
                logger.warning(
                    f"[Pipeline] Classroom {classroom_id} - Presentation Attack Blocked! "
                    f"BBox: {bbox_dict}, Reason: {spoof_res.reason}"
                )
                match_res = MatchResult(
                    student_id=None,
                    roll_no=None,
                    name=None,
                    department=None,
                    year=None,
                    similarity_score=0.0,
                    status_tier="unmarked"
                )
                rec = SingleFaceRecognition(
                    bbox=bbox_dict,
                    detector_confidence=face.confidence,
                    is_spoof=True,
                    liveness_score=spoof_res.liveness_score,
                    match_result=match_res,
                    student_id=None,
                    confidence_score=0.0,
                    status_tier="unmarked"
                )
                recognitions.append(rec)

                if period_id is not None:
                    raw_event = RecognitionEvent(
                        period_id=period_id,
                        classroom_id=classroom_id,
                        student_id=None,
                        confidence_score=0.0,
                        is_spoof_flagged=True,
                        bounding_box=bbox_dict,
                        frame_timestamp=ts
                    )
                    raw_events.append(raw_event)
                continue

            # 4. Extract ArcFace 512-dim Embedding
            embedding_vec = self.recognizer.extract_embedding(face.aligned_chip)

            # 5. Search pgvector Database via Cosine Similarity (<=> operator)
            match_res = self.recognizer.search_student_by_embedding(db, embedding_vec, top_k=1)

            rec = SingleFaceRecognition(
                bbox=bbox_dict,
                detector_confidence=face.confidence,
                is_spoof=False,
                liveness_score=spoof_res.liveness_score,
                match_result=match_res,
                student_id=match_res.student_id,
                confidence_score=match_res.similarity_score,
                status_tier=match_res.status_tier
            )
            recognitions.append(rec)

            # 6. Append-Only Raw Event Audit Record
            if period_id is not None:
                raw_event = RecognitionEvent(
                    period_id=period_id,
                    classroom_id=classroom_id,
                    student_id=match_res.student_id,
                    confidence_score=match_res.similarity_score,
                    is_spoof_flagged=False,
                    bounding_box=bbox_dict,
                    frame_timestamp=ts
                )
                raw_events.append(raw_event)

        return FrameRecognitionResult(
            classroom_id=classroom_id,
            frame_timestamp=ts,
            frame_number=frame_data.frame_number,
            faces_detected_count=len(detected_faces),
            recognitions=recognitions,
            raw_events=raw_events
        )
