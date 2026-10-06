"""
Centroid Face Tracker & Entry/Exit Logging Module.

Why Centroid Tracking is Used:
1. Entry & Exit Timestamps: CCTV cameras capture students throughout the period. 
   Tracking a face bounding box across time logs the EXACT moment a student enters 
   the classroom (first_seen) and leaves (last_seen).
2. Compute Optimization: Extracting 512-dim ArcFace embeddings for 30 students every 
   second consumes massive GPU/CPU power. Centroid tracking assigns an ongoing track ID; 
   once a track is recognized with high confidence ('confirmed'), we skip heavy recognition 
   on subsequent frames and simply update their last_seen exit timestamp.
"""

import math
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import numpy as np

logger = logging.getLogger("attendance.tracker")


@dataclass
class TrackedFace:
    """
    State of a persistently tracked student face in the classroom.
    
    Fields:
        object_id: Unique integer assigned to this continuous visual track.
        centroid: Current (cx, cy) center coordinate of the face.
        bbox: Current bounding box (x, y, w, h).
        first_seen: UTC timestamp when this track first appeared (Student Entry Time).
        last_seen: UTC timestamp of the most recent frame containing this track (Student Exit Time).
        disappeared_count: Number of consecutive sampled frames this track was missing.
        student_id: Matched student ID (if already recognized), else None.
        confidence: Highest recognition similarity score observed for this track.
        status_tier: 'confirmed', 'needs_review', or 'unmarked'.
        is_identified: True if student identity has been established.
    """
    object_id: int
    centroid: Tuple[int, int]
    bbox: Tuple[int, int, int, int]
    first_seen: datetime
    last_seen: datetime
    disappeared_count: int = 0
    student_id: Optional[int] = None
    confidence: float = 0.0
    status_tier: str = "unmarked"
    is_identified: bool = False


class CentroidTracker:
    """
    Lightweight, high-speed 2D centroid tracker for associating student face detections across video frames.
    
    How Centroid Tracking Works:
    1. Centroid Computation: For each bounding box (x, y, w, h), compute center cx = x + w/2, cy = y + h/2.
    2. Distance Matrix: Compute Euclidean distance between all existing track centroids and new frame centroids.
    3. Optimal Assignment: Greedily pair existing tracks with new detections starting from the smallest distance.
    4. Lifecycle Management: 
       - New detections without matches are registered as new tracks (Entry event).
       - Existing tracks not matched for 'max_disappeared' frames are deregistered (Exit finalized).
    """

    def __init__(self, max_disappeared: int = 15, max_distance: float = 120.0):
        """
        Initialize the Centroid Tracker.

        Args:
            max_disappeared: Number of consecutive frames a track can be missing before being deregistered.
                Why 15 frames: At 2.0 sampled FPS, 15 frames corresponds to 7.5 seconds. If a student turns 
                their head away from the camera for 3-5 seconds, the track is preserved without creating a duplicate.
            max_distance: Maximum allowable Euclidean pixel distance between centroids in adjacent frames.
                Why 120 pixels: Prevents jumping identities between two students sitting adjacent to each other.
        """
        self.next_object_id = 1
        self.objects: Dict[int, TrackedFace] = {}
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def _register(self, centroid: Tuple[int, int], bbox: Tuple[int, int, int, int], timestamp: datetime) -> int:
        """Registers a newly detected face as a new TrackedFace object."""
        obj_id = self.next_object_id
        self.next_object_id += 1
        self.objects[obj_id] = TrackedFace(
            object_id=obj_id,
            centroid=centroid,
            bbox=bbox,
            first_seen=timestamp,
            last_seen=timestamp,
            disappeared_count=0
        )
        return obj_id

    def _deregister(self, object_id: int) -> Optional[TrackedFace]:
        """Removes a track that has exited or disappeared beyond max_disappeared frames."""
        return self.objects.pop(object_id, None)

    def update(
        self,
        bounding_boxes: List[Tuple[int, int, int, int]],
        timestamp: datetime
    ) -> Tuple[List[TrackedFace], List[TrackedFace]]:
        """
        Updates tracked face states with new detections from the current frame.

        Args:
            bounding_boxes: List of (x, y, w, h) bounding boxes in the current frame.
            timestamp: Capture timestamp of the frame.

        Returns:
            Tuple[active_tracks, deregistered_tracks]
        """
        deregistered_tracks: List[TrackedFace] = []

        # 1. Case A: No detections in current frame
        if len(bounding_boxes) == 0:
            for obj_id in list(self.objects.keys()):
                self.objects[obj_id].disappeared_count += 1
                if self.objects[obj_id].disappeared_count > self.max_disappeared:
                    expired = self._deregister(obj_id)
                    if expired:
                        deregistered_tracks.append(expired)
            return list(self.objects.values()), deregistered_tracks

        # 2. Compute centroids for all input bounding boxes
        input_centroids = np.zeros((len(bounding_boxes), 2), dtype=int)
        for i, (x, y, w, h) in enumerate(bounding_boxes):
            cx = int(x + (w / 2.0))
            cy = int(y + (h / 2.0))
            input_centroids[i] = (cx, cy)

        # 3. Case B: No existing tracks; register all detections
        if len(self.objects) == 0:
            for i in range(len(bounding_boxes)):
                self._register(
                    centroid=(int(input_centroids[i][0]), int(input_centroids[i][1])),
                    bbox=bounding_boxes[i],
                    timestamp=timestamp
                )
            return list(self.objects.values()), deregistered_tracks

        # 4. Case C: Match existing tracks with new detections using Euclidean distance
        object_ids = list(self.objects.keys())
        object_centroids = np.array([self.objects[oid].centroid for oid in object_ids])

        # Compute Euclidean distance matrix shape (num_existing_objects, num_input_detections)
        # D[i, j] is the pixel distance between existing track i and new detection j
        dist_matrix = np.linalg.norm(object_centroids[:, np.newaxis] - input_centroids, axis=2)

        # Sort matrix rows by minimum distance to greedily match closest pairs
        row_indices = dist_matrix.min(axis=1).argsort()
        col_indices = dist_matrix.argmin(axis=1)[row_indices]

        used_rows = set()
        used_cols = set()

        for row, col in zip(row_indices, col_indices):
            if row in used_rows or col in used_cols:
                continue

            # Reject match if distance exceeds spatial threshold (e.g. 120px)
            if dist_matrix[row, col] > self.max_distance:
                continue

            obj_id = object_ids[row]
            matched_centroid = (int(input_centroids[col][0]), int(input_centroids[col][1]))
            matched_bbox = bounding_boxes[col]

            # Update tracked object
            self.objects[obj_id].centroid = matched_centroid
            self.objects[obj_id].bbox = matched_bbox
            self.objects[obj_id].last_seen = timestamp
            self.objects[obj_id].disappeared_count = 0

            used_rows.add(row)
            used_cols.add(col)

        # 5. Handle unmatched existing tracks (increment disappeared count)
        unused_rows = set(range(len(object_ids))) - used_rows
        for row in unused_rows:
            obj_id = object_ids[row]
            self.objects[obj_id].disappeared_count += 1
            if self.objects[obj_id].disappeared_count > self.max_disappeared:
                expired = self._deregister(obj_id)
                if expired:
                    deregistered_tracks.append(expired)

        # 6. Handle unmatched new detections (register as new tracks)
        unused_cols = set(range(len(bounding_boxes))) - used_cols
        for col in unused_cols:
            self._register(
                centroid=(int(input_centroids[col][0]), int(input_centroids[col][1])),
                bbox=bounding_boxes[col],
                timestamp=timestamp
            )

        return list(self.objects.values()), deregistered_tracks

    def associate_recognition(
        self,
        object_id: int,
        student_id: Optional[int],
        confidence: float,
        status_tier: str
    ) -> None:
        """
        Attaches facial recognition output to an active track.
        """
        if object_id in self.objects:
            track = self.objects[object_id]
            if confidence > track.confidence:
                track.confidence = confidence
                track.student_id = student_id
                track.status_tier = status_tier
                if status_tier == "confirmed":
                    track.is_identified = True
