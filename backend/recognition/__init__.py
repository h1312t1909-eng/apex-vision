"""
Face Recognition, Detection, and Anti-Spoofing Pipeline.

This package provides:
1. Multi-face detection (SCRFD / YuNet) for classroom CCTV frames.
2. Silent-Face Anti-Spoofing (MiniFASNet / texture liveness) to prevent presentation attacks.
3. ArcFace (Buffalo_L) 512-dimensional embedding extraction and pgvector cosine search.
4. Multi-angle / multi-lighting student enrollment pipeline.
5. End-to-end unified recognition pipeline.
"""

from backend.recognition.face_detector import FaceDetector, DetectedFace
from backend.recognition.anti_spoofing import AntiSpoofDetector, SpoofCheckResult
from backend.recognition.face_recognizer import FaceRecognizer, MatchResult
from backend.recognition.enrollment import EnrollmentService
from backend.recognition.pipeline import RecognitionPipeline, FrameRecognitionResult

__all__ = [
    "FaceDetector",
    "DetectedFace",
    "AntiSpoofDetector",
    "SpoofCheckResult",
    "FaceRecognizer",
    "MatchResult",
    "EnrollmentService",
    "RecognitionPipeline",
    "FrameRecognitionResult",
]
