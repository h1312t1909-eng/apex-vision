"""
Camera Ingestion Module for CCTV-based Automated Student Attendance System.

Provides robust RTSP streaming with:
1. Dedicated background reader threads per camera to eliminate RTSP frame buffer latency.
2. Exponential backoff auto-reconnect logic on dropped network streams.
3. Controlled FPS frame sampling to optimize inference pipeline throughput.
4. Multi-camera lifecycle management for managing multiple classrooms concurrently.
"""

from backend.camera_ingestion.stream_capture import RTSPCameraStream, FrameData
from backend.camera_ingestion.camera_manager import CameraManager

__all__ = ["RTSPCameraStream", "FrameData", "CameraManager"]
