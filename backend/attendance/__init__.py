"""
Attendance Processing, Tracking, and Deduplication Module.

This package provides:
1. Centroid Face Tracker for maintaining object identity and tracking student entry & exit times.
2. Redis-based real-time deduplication to prevent database write bottlenecks.
3. Period boundary resolver and timetable lifecycle management.
4. Confidence-tiered attendance state machine ('confirmed', 'needs_review', 'unmarked', 'absent').
5. Faculty manual override management with immutable audit trail logging.
"""

from backend.attendance.tracker import CentroidTracker, TrackedFace
from backend.attendance.dedup import AttendanceDeduplicator
from backend.attendance.period_service import PeriodService
from backend.attendance.attendance_processor import AttendanceProcessor

__all__ = [
    "CentroidTracker",
    "TrackedFace",
    "AttendanceDeduplicator",
    "PeriodService",
    "AttendanceProcessor"
]
