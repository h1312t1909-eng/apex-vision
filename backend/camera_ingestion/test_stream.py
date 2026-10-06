"""
Camera Ingestion Verification and Demo Test Script.

Why this script:
Allows running a standalone test of RTSPCameraStream and CameraManager using 
a local webcam (index 0) or synthetic frame generation if no physical RTSP IP camera 
is connected during the hackathon demo.
"""

import time
import logging
import cv2
import numpy as np
from backend.camera_ingestion.stream_capture import RTSPCameraStream, FrameData
from backend.camera_ingestion.camera_manager import CameraManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_stream")


def create_synthetic_classroom_frame(frame_num: int, classroom_name: str) -> np.ndarray:
    """Creates a mock video frame showing timestamp and classroom name."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (35, 35, 35) # Dark gray background

    # Draw mock blackboard
    cv2.rectangle(img, (50, 40), (590, 200), (20, 60, 20), -1)
    cv2.putText(img, f"Classroom: {classroom_name}", (70, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(img, f"Simulated CCTV Feed - Frame #{frame_num}", (70, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 255, 180), 1)

    # Draw timestamp
    cv2.putText(img, time.strftime("%Y-%m-%d %H:%M:%S"), (50, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    return img


def run_test():
    logger.info("Initializing CameraManager...")
    manager = CameraManager(frame_queue_maxsize=50, default_target_fps=2.0)

    # Register Classroom 1 (can use webcam "0" or synthetic test)
    manager.register_camera(classroom_id=1, camera_url="0", target_fps=2.0)

    logger.info("Starting cameras...")
    manager.start_all_cameras()

    logger.info("Listening for sampled frames from queue for 5 seconds...")
    start_time = time.time()
    frames_received = 0

    while time.time() - start_time < 5.0:
        frame_data = manager.get_next_frame(block=True, timeout=0.5)
        if frame_data:
            frames_received += 1
            logger.info(
                f"-> Received Frame #{frame_data.frame_number} from Classroom {frame_data.classroom_id} "
                f"at {frame_data.timestamp.strftime('%H:%M:%S.%f')[:-3]} (Shape: {frame_data.frame.shape})"
            )

    logger.info(f"Total frames sampled and processed in 5 seconds: {frames_received}")
    status = manager.get_camera_status()
    logger.info(f"Camera Telemetry: {status}")

    logger.info("Stopping all cameras...")
    manager.stop_all_cameras()
    logger.info("Stage 2 Camera Ingestion test complete!")


if __name__ == "__main__":
    run_test()
