"""
Multi-Camera Ingestion Lifecycle Manager.

Why this manager is needed:
A college campus has multiple classrooms operating simultaneously. The CameraManager:
1. Dynamically discovers configured classrooms and spawns one worker thread per camera.
2. Aggregates sampled frames from all cameras into a unified, thread-safe processing queue.
3. Exposes real-time stream health telemetry (FPS, connection state, reconnect counts)
   for the live admin/faculty dashboard.
"""

import logging
import queue
import threading
from typing import Dict, List, Optional, Callable, Any
from backend.camera_ingestion.stream_capture import RTSPCameraStream, FrameData

logger = logging.getLogger("camera_ingestion.manager")


class CameraManager:
    """
    Coordinates and monitors all active classroom RTSP camera ingestion streams.
    """

    def __init__(
        self,
        frame_queue_maxsize: int = 100,
        default_target_fps: float = 2.0,
        reconnect_interval_sec: float = 5.0
    ):
        """
        Initialize the Camera Manager.

        Args:
            frame_queue_maxsize: Maximum number of frames held in the downstream queue.
                Why bounded queue: Prevents runaway memory usage if deep learning inference
                temporarily slows down.
            default_target_fps: Default sampled FPS across cameras (e.g. 2.0 fps).
            reconnect_interval_sec: Delay between reconnect attempts.
        """
        self.default_target_fps = default_target_fps
        self.reconnect_interval_sec = reconnect_interval_sec
        self.frame_queue: queue.Queue[FrameData] = queue.Queue(maxsize=frame_queue_maxsize)
        
        # Dictionary mapping classroom_id -> RTSPCameraStream instance
        self._streams: Dict[int, RTSPCameraStream] = {}
        self._lock = threading.Lock()

    def register_camera(
        self,
        classroom_id: int,
        camera_url: str,
        target_fps: Optional[float] = None
    ) -> RTSPCameraStream:
        """
        Registers and creates a camera stream worker for a classroom.

        Args:
            classroom_id: ID of the classroom.
            camera_url: RTSP URL, video file path, or webcam index (e.g. "0").
            target_fps: Optional custom FPS override for this specific camera.

        Returns:
            RTSPCameraStream instance.
        """
        fps = target_fps or self.default_target_fps

        with self._lock:
            # If a stream already exists for this classroom, stop and replace it
            if classroom_id in self._streams:
                logger.info(f"[Manager] Updating existing stream for classroom {classroom_id}...")
                self._streams[classroom_id].stop()

            stream = RTSPCameraStream(
                classroom_id=classroom_id,
                camera_url=camera_url,
                target_fps=fps,
                reconnect_interval_sec=self.reconnect_interval_sec,
                on_frame_callback=self._handle_frame_received
            )
            self._streams[classroom_id] = stream
            logger.info(f"[Manager] Registered camera for classroom {classroom_id}: {camera_url} @ {fps} FPS")
            return stream

    def start_camera(self, classroom_id: int) -> bool:
        """Starts streaming from a registered camera."""
        with self._lock:
            stream = self._streams.get(classroom_id)
            if not stream:
                logger.warning(f"[Manager] Cannot start camera for classroom {classroom_id}: Not registered.")
                return False
            stream.start()
            return True

    def start_all_cameras(self) -> None:
        """Starts all registered camera stream workers."""
        with self._lock:
            for classroom_id, stream in self._streams.items():
                logger.info(f"[Manager] Starting camera for classroom {classroom_id}...")
                stream.start()

    def stop_camera(self, classroom_id: int) -> bool:
        """Stops streaming from a specific camera."""
        with self._lock:
            stream = self._streams.get(classroom_id)
            if not stream:
                return False
            stream.stop()
            return True

    def stop_all_cameras(self) -> None:
        """Stops all running camera streams cleanly."""
        with self._lock:
            logger.info("[Manager] Stopping all camera workers...")
            for classroom_id, stream in self._streams.items():
                stream.stop()

    def get_next_frame(self, block: bool = True, timeout: Optional[float] = 1.0) -> Optional[FrameData]:
        """
        Pulls the next sampled frame from any camera from the unified queue.
        
        Why unified queue:
        Downstream face detection and recognition workers consume from this single
        queue in a producer-consumer pattern, ensuring linear, ordered processing.
        """
        try:
            return self.frame_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def get_camera_status(self) -> List[Dict[str, Any]]:
        """
        Returns status and health telemetry for all managed cameras.
        Used by the live monitoring API and dashboard.
        """
        statuses = []
        with self._lock:
            for classroom_id, stream in self._streams.items():
                statuses.append({
                    "classroom_id": classroom_id,
                    "camera_url": stream.camera_url,
                    "is_connected": stream.is_connected,
                    "total_frames_read": stream.total_frames_read,
                    "total_frames_sampled": stream.total_frames_sampled,
                    "reconnect_count": stream.reconnect_count,
                    "last_error": stream.last_error_message
                })
        return statuses

    def _handle_frame_received(self, frame_data: FrameData) -> None:
        """
        Internal callback triggered by RTSPCameraStream whenever a new frame is sampled.
        Pushes the frame into the processing queue with overflow protection.
        """
        try:
            # Non-blocking put: if the queue is full (downstream is bogged down),
            # discard the oldest frame or drop the new frame to prioritize real-time recency.
            if self.frame_queue.full():
                try:
                    _ = self.frame_queue.get_nowait() # Discard stale frame
                except queue.Empty:
                    pass
            self.frame_queue.put_nowait(frame_data)
        except Exception as exc:
            logger.error(f"[Manager] Error enqueueing frame for classroom {frame_data.classroom_id}: {exc}")
