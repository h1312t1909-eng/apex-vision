# 🎓 CCTV-Based Automated Student Attendance System

> An end-to-end, multi-camera, real-time facial recognition attendance system designed for university lecture halls and college hackathons. Replaces manual paper registers and card-swiping with automated RTSP ingestion, deep-learning anti-spoofing, ArcFace embeddings search in PostgreSQL `pgvector`, centroid tracking, and a live WebSocket React dashboard.

---

## 🏗️ Architecture & Pipeline Overview

```
 [ Classroom CCTV Cameras ]  (RTSP Stream / 1080p @ 30 FPS)
              │
              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Camera Ingestion Module (camera_ingestion/)             │
 │  - Dedicated reader thread per camera (prevents lag)     │
 │  - Exponential backoff auto-reconnect on network drops    │
 │  - 2.0 FPS sampling governor (saves 93% compute)        │
 └────────────────────────────┬─────────────────────────────┘
                              │ Sampled Frame
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Face Detection & Anti-Spoofing (recognition/)           │
 │  - Multi-Face Detection: SCRFD / YuNet (returns all)     │
 │  - MiniFASNet Liveness: Blocks printed photos & screens  │
 │  - ArcFace (Buffalo_L): 512-dim normalized embeddings    │
 └────────────────────────────┬─────────────────────────────┘
                              │ Embeddings
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Database & Matching (database/)                         │
 │  - PostgreSQL + pgvector HNSW index (<=> Cosine Distance)│
 │  - Confirmed (>= 0.68) | Needs Review (0.50-0.68)        │
 └────────────────────────────┬─────────────────────────────┘
                              │ Match Results
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Attendance & Tracking Engine (attendance/)              │
 │  - Centroid Tracker: Computes exact Entry & Exit times   │
 │  - Redis Dedup: Suppresses duplicate writes per period   │
 │  - Timetable Boundaries: start_time <= now <= end_time   │
 │  - Teacher Overrides: Immutable justification audit log  │
 └────────────────────────────┬─────────────────────────────┘
                              │ State Updates
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  FastAPI WebSocket & REST API (api/)                     │
 │  - Sub-50ms push of recognitions & spoof alerts          │
 │  - Official Excel (.xlsx) Report Generator (reports/)    │
 └────────────────────────────┬─────────────────────────────┘
                              │ WebSocket / JSON
                              ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Apex University Live React Dashboard (frontend/)        │
 │  - Real-time present/absent grid & KPI statistics        │
 │  - One-click faculty review & manual override modal      │
 │  - 8-10 photo multi-angle student enrollment wizard      │
 └──────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema Design

| Table Name | Primary Purpose | Key Fields / Indexes |
| :--- | :--- | :--- |
| **`students`** | Master student records | `id`, `roll_no` (UNIQUE), `name`, `department`, `year` |
| **`face_embeddings`** | Reference face vectors | `embedding VECTOR(512)`, `angle_label`, `lighting_label`, **HNSW Cosine Index** |
| **`teachers`** | Faculty masters | `id`, `name`, `email` (UNIQUE), `department` |
| **`classrooms`** | Physical room mappings | `id`, `name` (UNIQUE), `camera_rtsp_url`, `location` |
| **`periods`** | Timetable slots | `classroom_id`, `teacher_id`, `subject`, `period_date`, `start_time`, `end_time` |
| **`recognition_events`** | Raw forensic audit log | `period_id`, `student_id` (nullable), `confidence_score`, `is_spoof_flagged`, `bounding_box` (JSONB) |
| **`attendance_records`** | Clean derived state | `student_id`, `period_id`, `status`, `entry_time`, `exit_time`, `marked_by`, **UNIQUE(student_id, period_id)** |
| **`teacher_overrides`** | Faculty audit trail | `attendance_record_id`, `teacher_id`, `previous_status`, `new_status`, `reason`, `overridden_at` |

---

## 🚀 Quickstart & Setup Guide

### 1. Start PostgreSQL (with pgvector) & Redis
```bash
docker compose up -d
```

### 2. Backend Setup & Seeding
```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate   # On Windows (or source venv/bin/activate on Linux/Mac)

# Install backend dependencies
pip install -r backend/requirements.txt

# Run initial migrations and seed demo students/classrooms
python -m backend.database.seed

# Start FastAPI backend server
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation is available at: `http://localhost:8000/docs`

### 3. Frontend Setup & Run
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000` in your browser.

---

## 💡 How to Walk Judges Through the Project

1. **The Database & Vector Layer**:
   - Point to [`001_initial_schema.sql`](file:///C:/PROJECTS/base_model-main/backend/database/migrations/001_initial_schema.sql).
   - Explain why `VECTOR(512)` with the **HNSW Index** using `vector_cosine_ops` allows sub-millisecond similarity search directly inside PostgreSQL.
   - Show how storing 8–10 multi-angle embeddings per student overcomes CCTV pitch angles.

2. **RTSP Camera Ingestion & Lag Elimination**:
   - Open [`stream_capture.py`](file:///C:/PROJECTS/base_model-main/backend/camera_ingestion/stream_capture.py).
   - Explain why standard OpenCV loops accumulate multi-second lag and how our dedicated background reader thread with 1-frame buffer solves it.
   - Explain why 2.0 FPS sampling captures moving students 4–6 times while reducing compute by 93%.

3. **Anti-Spoofing & Deep Recognition**:
   - Open [`anti_spoofing.py`](file:///C:/PROJECTS/base_model-main/backend/recognition/anti_spoofing.py) & [`face_recognizer.py`](file:///C:/PROJECTS/base_model-main/backend/recognition/face_recognizer.py).
   - Explain how MiniFASNet and Fourier frequency analysis block 2D paper and screen spoof attempts.
   - Explain confidence tiers: Confirmed ($\ge 68\%$), Needs Review ($50\% - 68\%$), and Unmarked ($< 50\%$).

4. **Tracking, Redis Dedup & Timetable Boundaries**:
   - Open [`tracker.py`](file:///C:/PROJECTS/base_model-main/backend/attendance/tracker.py) & [`dedup.py`](file:///C:/PROJECTS/base_model-main/backend/attendance/dedup.py).
   - Show how the Centroid Tracker captures exact `entry_time` and `exit_time`.
   - Show how Redis deduplication prevents redundant database updates across 30 FPS camera frames.

5. **Live University Dashboard & One-Click Faculty Review**:
   - Open `http://localhost:3000` to demo the live attendance grid, WebSocket activity feed, one-click faculty confirmation, manual override modal with compulsory justification reason, and Excel report export.
