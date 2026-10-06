"""
Multi-Face Detection Module (SCRFD / YuNet).

Why Multi-Face Detection is Standard (not a special case):
In a classroom CCTV scenario, a single wide-angle camera frame captured at 1080p or 4K 
routinely contains between 10 to 40 students simultaneously. The face detector must 
locate every face in one forward inference pass, after which each detected face is 
passed through the anti-spoofing and ArcFace recognition pipeline independently.
"""

import os
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
import cv2
import numpy as np

logger = logging.getLogger("recognition.detector")


@dataclass
class DetectedFace:
    """
    Data structure representing a single detected face in a camera frame.
    
    Fields:
        bbox: Bounding box tuple (x, y, w, h) in original frame pixel coordinates.
        confidence: Detection score from 0.0 to 1.0 (thresholded >= 0.50).
        landmarks: 5 facial keypoints [(left_eye), (right_eye), (nose), (left_mouth), (right_mouth)] for alignment.
        aligned_chip: 112x112 aligned RGB crop of the face ready for ArcFace feature extraction.
        raw_crop: Unaligned crop used for anti-spoofing texture/frequency analysis.
    """
    bbox: Tuple[int, int, int, int]
    confidence: float
    landmarks: Optional[np.ndarray]
    aligned_chip: np.ndarray
    raw_crop: np.ndarray


class FaceDetector:
    """
    Multi-face detector supporting SCRFD / YuNet / OpenCV backends.
    
    Why SCRFD / YuNet over older Haar/HOG cascades:
    1. Scale Invariance: Classrooms have students sitting in the front row (large faces ~150px)
       and back rows (small faces ~30-40px). SCRFD uses Feature Pyramid Networks (FPN) 
       optimized for tiny and medium scale faces.
    2. Occlusion Robustness: Accurately detects faces with partial occlusions (masks, hands, glasses).
    3. 5-Point Landmark Alignment: Outputs eyes, nose, and mouth corners required to align faces
       to canonical 112x112 coordinates before ArcFace embedding extraction.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.50,
        nms_threshold: float = 0.40,
        input_size: Tuple[int, int] = (640, 640)
    ):
        """
        Initialize the multi-face detector.

        Args:
            confidence_threshold: Minimum detection confidence score (default 0.50).
                Why 0.50: Balances recall for back-row students while eliminating false positives on classroom objects.
            nms_threshold: Non-Maximum Suppression overlap threshold to remove duplicate bounding boxes.
            input_size: Network input resolution (width, height) for image resizing.
        """
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self._insightface_app = None
        self._yunet_detector = None
        self._cascade_fallback = None

        self._initialize_detector_backend()

    def _initialize_detector_backend(self) -> None:
        """
        Attempts to initialize InsightFace (SCRFD), falling back to OpenCV YuNet or Haar Cascades
        if model weights or CUDA/ONNX providers are absent in lightweight test environments.
        """
        # 1. Try initializing InsightFace FaceAnalysis (SCRFD)
        try:
            import insightface
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection"])
            app.prepare(ctx_id=-1, det_size=self.input_size) # ctx_id=-1 uses CPU, >=0 uses GPU
            self._insightface_app = app
            logger.info("[FaceDetector] Initialized InsightFace SCRFD multi-face detector.")
            return
        except Exception as exc:
            logger.warning(f"[FaceDetector] InsightFace initialization unavailable: {exc}. Trying OpenCV YuNet...")

        # 2. Try OpenCV DNN YuNet (Built into OpenCV 4.5.4+)
        try:
            # Check for standard yunet onnx model or use cv2.FaceDetectorYN
            yunet_model_path = os.getenv("YUNET_MODEL_PATH", "models/face_detection_yunet_2023mar.onnx")
            if os.path.exists(yunet_model_path):
                self._yunet_detector = cv2.FaceDetectorYN.create(
                    model=yunet_model_path,
                    config="",
                    input_size=self.input_size,
                    score_threshold=self.confidence_threshold,
                    nms_threshold=self.nms_threshold,
                    top_k=5000
                )
                logger.info("[FaceDetector] Initialized OpenCV YuNet face detector.")
                return
        except Exception as exc:
            logger.warning(f"[FaceDetector] OpenCV YuNet unavailable: {exc}. Falling back to OpenCV Cascade...")

        # 3. Fallback: OpenCV Haar Cascade for universal compatibility during offline testing
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        if os.path.exists(cascade_path):
            self._cascade_fallback = cv2.CascadeClassifier(cascade_path)
            logger.info("[FaceDetector] Initialized OpenCV Haar Cascade fallback detector.")
        else:
            logger.warning("[FaceDetector] No detector weights found; synthetic detector will be used.")

    def detect_faces(self, image: np.ndarray) -> List[DetectedFace]:
        """
        Detects all faces in a single frame.

        Args:
            image: BGR input image from camera (np.ndarray).

        Returns:
            List[DetectedFace]: All detected faces in the frame.
        """
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]

        # Mode A: InsightFace SCRFD
        if self._insightface_app is not None:
            return self._detect_insightface(image)

        # Mode B: OpenCV YuNet
        if self._yunet_detector is not None:
            return self._detect_yunet(image, w, h)

        # Mode C: Fallback Haar Cascade
        if self._cascade_fallback is not None:
            return self._detect_cascade(image)

        # Mode D: Emergency mock detector for tests
        return []

    def _detect_insightface(self, image: np.ndarray) -> List[DetectedFace]:
        """Runs InsightFace SCRFD detector."""
        detected = []
        # InsightFace expects BGR image directly
        faces = self._insightface_app.get(image)
        for face in faces:
            if face.det_score < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = [int(v) for v in face.bbox]
            # Clip bbox to image bounds
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(image.shape[1], x2)
            y2 = min(image.shape[0], y2)
            bw = max(1, x2 - x1)
            bh = max(1, y2 - y1)

            raw_crop = image[y1:y2, x1:x2]
            # Align face if landmarks (kps) exist, or resize
            aligned = self._align_face(image, face.kps) if hasattr(face, "kps") and face.kps is not None else cv2.resize(raw_crop, (112, 112))

            detected.append(DetectedFace(
                bbox=(x1, y1, bw, bh),
                confidence=float(face.det_score),
                landmarks=face.kps if hasattr(face, "kps") else None,
                aligned_chip=aligned,
                raw_crop=raw_crop
            ))
        return detected

    def _detect_yunet(self, image: np.ndarray, w: int, h: int) -> List[DetectedFace]:
        """Runs OpenCV YuNet DNN detector."""
        self._yunet_detector.setInputSize((w, h))
        _, faces = self._yunet_detector.detect(image)
        if faces is None:
            return []

        detected = []
        for face in faces:
            score = float(face[14])
            if score < self.confidence_threshold:
                continue

            x, y, bw, bh = [int(v) for v in face[0:4]]
            x = max(0, x)
            y = max(0, y)
            bw = min(w - x, bw)
            bh = min(h - y, bh)

            if bw <= 10 or bh <= 10:
                continue

            landmarks = np.array([
                [face[4], face[5]],   # Right eye
                [face[6], face[7]],   # Left eye
                [face[8], face[9]],   # Nose tip
                [face[10], face[11]], # Right mouth corner
                [face[12], face[13]], # Left mouth corner
            ], dtype=np.float32)

            raw_crop = image[y:y+bh, x:x+bw]
            aligned = self._align_face(image, landmarks)

            detected.append(DetectedFace(
                bbox=(x, y, bw, bh),
                confidence=score,
                landmarks=landmarks,
                aligned_chip=aligned,
                raw_crop=raw_crop
            ))
        return detected

    def _detect_cascade(self, image: np.ndarray) -> List[DetectedFace]:
        """Fallback Haar cascade multi-face detector."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        boxes = self._cascade_fallback.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        detected = []
        for (x, y, bw, bh) in boxes:
            raw_crop = image[y:y+bh, x:x+bw]
            aligned = cv2.resize(raw_crop, (112, 112))
            detected.append(DetectedFace(
                bbox=(int(x), int(y), int(bw), int(bh)),
                confidence=0.85, # Synthetic confidence for Haar
                landmarks=None,
                aligned_chip=aligned,
                raw_crop=raw_crop
            ))
        return detected

    @staticmethod
    def _align_face(image: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        """
        Performs 2D Similarity Transformation (Umeyama algorithm) to map 5 facial landmarks 
        to canonical ArcFace 112x112 reference coordinates.
        
        Why Landmark Alignment is Critical:
        ArcFace deep convolutional networks are trained on strictly aligned face crops where 
        the left eye is at ~(38.29, 51.69) and right eye is at ~(73.53, 51.69).
        Proper alignment removes head tilt/roll angle, increasing recognition accuracy by ~15-20%.
        """
        # Standard ArcFace canonical 5-point reference landmarks for 112x112 resolution
        src_pts = np.array([
            [38.2946, 51.6963],
            [73.5318, 51.6963],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.3655]
        ], dtype=np.float32)

        if landmarks is None or len(landmarks) != 5:
            # Cannot compute affine matrix without 5 points; return simple resize
            return cv2.resize(image, (112, 112))

        try:
            # Estimate similarity transform matrix (rotation, uniform scale, translation)
            tform, _ = cv2.estimateAffinePartial2D(landmarks, src_pts)
            if tform is None:
                return cv2.resize(image, (112, 112))
            aligned_face = cv2.warpAffine(image, tform, (112, 112), borderValue=0.0)
            return aligned_face
        except Exception:
            return cv2.resize(image, (112, 112))
