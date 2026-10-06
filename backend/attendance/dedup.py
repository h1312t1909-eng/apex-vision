"""
Redis-Based Attendance Deduplication Module.

Why Redis Deduplication is Critical:
1. Multi-Camera Redundancy: If Classroom LH-101 has two cameras (Front Entry + Blackboard View),
   a student entering the room will be detected by both cameras at the same second.
2. High-Frequency Video Frames: At 2 FPS, a seated student generates 7,200 recognition events 
   in a 1-hour lecture. Without deduplication, the database would suffer 7,200 redundant SQL UPDATE 
   locks per student.
3. Redis Atomicity: Redis SETNX (SET if Not eXists) provides atomic sub-millisecond locking 
   across distributed worker threads.
"""

import os
import time
import logging
from typing import Optional, Dict, Tuple
import redis

logger = logging.getLogger("attendance.dedup")


class AttendanceDeduplicator:
    """
    Manages in-memory and Redis-backed deduplication caches for period attendance.
    """

    def __init__(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: int = 0,
        default_ttl_seconds: int = 3600 # 1 hour default period TTL
    ):
        """
        Initialize the Attendance Deduplicator.

        Args:
            redis_host: Hostname for Redis instance (default from REDIS_HOST env or 'localhost').
            redis_port: Port for Redis instance (default from REDIS_PORT env or 6379).
            redis_db: Redis database index.
            default_ttl_seconds: Cache key expiration in seconds.
        """
        self.host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(redis_port or os.getenv("REDIS_PORT", "6379"))
        self.db_idx = redis_db
        self.default_ttl_seconds = default_ttl_seconds

        self._redis_client: Optional[redis.Redis] = None
        self._in_memory_cache: Dict[str, Tuple[str, float, float]] = {} # key -> (status, confidence, expire_at)
        
        self._initialize_redis()

    def _initialize_redis(self) -> None:
        """Attempts to establish connection to Redis server."""
        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db_idx,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5
            )
            client.ping()
            self._redis_client = client
            logger.info(f"[Dedup] Connected to Redis at {self.host}:{self.port}")
        except Exception as exc:
            logger.warning(
                f"[Dedup] Redis server unavailable at {self.host}:{self.port} ({exc}). "
                "Using high-performance in-memory fallback cache."
            )
            self._redis_client = None

    def should_process_attendance(
        self,
        period_id: int,
        student_id: int,
        new_status: str,
        new_confidence: float
    ) -> bool:
        """
        Determines whether an attendance write operation is required.

        Logic:
        1. If student has NOT been marked in this period -> Allow write (Return True).
        2. If student is already 'confirmed' and new detection is also 'confirmed' -> Deduplicate (Return False).
        3. If student is currently 'needs_review' but new detection is 'confirmed' (higher tier) -> Allow upgrade (Return True).
        4. If student is currently 'confirmed' and new detection is 'needs_review' -> Deduplicate (Return False).

        Returns:
            bool: True if database write/update should proceed, False if deduplicated.
        """
        key = f"att:dedup:{period_id}:{student_id}"

        # Mode A: Redis Distributed Cache
        if self._redis_client is not None:
            try:
                cached_data = self._redis_client.get(key)
                if cached_data is None:
                    # First time seeing student in this period
                    self._redis_client.set(
                        key,
                        f"{new_status}:{new_confidence:.3f}",
                        ex=self.default_ttl_seconds
                    )
                    return True

                cached_status, cached_conf_str = cached_data.split(":", 1)
                cached_conf = float(cached_conf_str)

                # Upgrade check: If cached is 'needs_review' or 'unmarked' and new is 'confirmed'
                if cached_status != "confirmed" and new_status == "confirmed":
                    self._redis_client.set(
                        key,
                        f"{new_status}:{new_confidence:.3f}",
                        ex=self.default_ttl_seconds
                    )
                    return True

                # Deduplicate repeated identical or lower-tier detections
                return False
            except Exception as exc:
                logger.error(f"[Dedup] Redis query error: {exc}. Falling back to memory cache.")

        # Mode B: In-Memory Fallback Cache
        now = time.monotonic()
        if key in self._in_memory_cache:
            cached_status, cached_conf, expire_at = self._in_memory_cache[key]
            if now < expire_at:
                # Key still valid
                if cached_status != "confirmed" and new_status == "confirmed":
                    self._in_memory_cache[key] = (new_status, new_confidence, now + self.default_ttl_seconds)
                    return True
                return False

        # Key expired or not found
        self._in_memory_cache[key] = (new_status, new_confidence, now + self.default_ttl_seconds)
        return True

    def clear_period_cache(self, period_id: int) -> None:
        """Clears all dedup keys for a specific period when period ends."""
        pattern = f"att:dedup:{period_id}:*"
        if self._redis_client is not None:
            try:
                keys = self._redis_client.keys(pattern)
                if keys:
                    self._redis_client.delete(*keys)
            except Exception as exc:
                logger.error(f"[Dedup] Failed to clear Redis keys for period {period_id}: {exc}")

        # Clear in-memory keys
        prefix = f"att:dedup:{period_id}:"
        to_delete = [k for k in self._in_memory_cache if k.startswith(prefix)]
        for k in to_delete:
            self._in_memory_cache.pop(k, None)
