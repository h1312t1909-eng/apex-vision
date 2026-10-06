-- ==============================================================================
-- DATABASE MIGRATION: 001_initial_schema.sql
-- PROJECT: CCTV-based Automated Student Attendance System
-- PURPOSE: 
--   Establishes core relational tables and pgvector extension for high-dimensional
--   face embedding similarity searches, raw recognition event auditing, derived
--   clean attendance states, and teacher manual override logging.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Enable pgvector Extension
-- Why: ArcFace (Buffalo_L) generates 512-dimensional normalized float vectors.
-- The pgvector extension adds a native 'vector(512)' data type in PostgreSQL,
-- allowing similarity search (cosine distance) to execute inside the DB engine
-- using SIMD-accelerated CPU instructions rather than fetching all embeddings into Python.
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------------------------
-- 2. Students Table
-- Why: Master record of enrolled students.
-- Each student has a unique roll_no used as their academic identifier across
-- college administration departments.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    roll_no VARCHAR(50) NOT NULL UNIQUE,       -- College roll / registration number (unique index automatically created)
    name VARCHAR(150) NOT NULL,                -- Full name of the student
    department VARCHAR(100) NOT NULL,          -- Academic department (e.g., 'Computer Science & Engineering')
    year INT NOT NULL CHECK (year >= 1 AND year <= 5), -- Academic year (1st to 4th/5th year)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index for searching students by department and year for section-level queries
CREATE INDEX IF NOT EXISTS idx_students_dept_year ON students(department, year);


-- ------------------------------------------------------------------------------
-- 3. Face Embeddings Table (pgvector 512-dim)
-- Why: Stores 8-10 reference face embedding vectors per student captured during
-- the enrollment flow under various angles (frontal, left 30°, right 30°, tilted)
-- and lighting conditions (bright, dim, natural).
-- By storing multiple vectors per student rather than averaging them, we achieve
-- high recognition accuracy across varying classroom CCTV angles.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS face_embeddings (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    embedding VECTOR(512) NOT NULL,            -- 512-dimensional normalized ArcFace embedding
    angle_label VARCHAR(50) NOT NULL,          -- e.g., 'frontal', 'left_30', 'right_30', 'upward', 'downward'
    lighting_label VARCHAR(50) NOT NULL,       -- e.g., 'normal', 'low_light', 'high_exposure'
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Foreign key lookup index: allows retrieving all enrollment vectors for a student fast
CREATE INDEX IF NOT EXISTS idx_face_embeddings_student_id ON face_embeddings(student_id);

-- Vector Index using HNSW (Hierarchical Navigable Small World) with Cosine Distance:
-- Why HNSW with vector_cosine_ops:
-- ArcFace embeddings are L2-normalized vectors on a hypersphere. Cosine distance 
-- (1 - cosine_similarity) is the mathematically exact metric for face identity matching.
-- HNSW provides sub-millisecond approximate nearest neighbor (ANN) lookups with high recall.
CREATE INDEX IF NOT EXISTS idx_face_embeddings_vector_hnsw 
ON face_embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);


-- ------------------------------------------------------------------------------
-- 4. Teachers Table
-- Why: Master record of faculty members responsible for overseeing classroom
-- periods, verifying low-confidence attendance, and making manual overrides.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teachers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,                -- Full name of faculty member
    email VARCHAR(255) NOT NULL UNIQUE,        -- Official institutional email
    department VARCHAR(100) NOT NULL           -- Faculty department
);


-- ------------------------------------------------------------------------------
-- 5. Classrooms Table
-- Why: Maps physical classroom spaces to their respective IP/CCTV camera RTSP feeds.
-- One classroom corresponds to one or more primary RTSP camera streams.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS classrooms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,         -- Human-readable classroom name (e.g., 'LH-101', 'CSE-Lab-3')
    camera_rtsp_url TEXT NOT NULL,             -- RTSP URL for CCTV camera (e.g., 'rtsp://admin:pass@192.168.1.50:554/stream1')
    location VARCHAR(255)                      -- Physical building/floor location
);


-- ------------------------------------------------------------------------------
-- 6. Periods Table
-- Why: Academic timetable slot defining when a lecture occurs in a specific
-- classroom for a specific subject by an assigned teacher.
-- PERIOD-BOUNDARY LOGIC:
-- Camera recognition events are only credited to attendance if frame_timestamp
-- falls between start_time and end_time on period_date.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS periods (
    id SERIAL PRIMARY KEY,
    classroom_id INT NOT NULL REFERENCES classrooms(id) ON DELETE RESTRICT,
    teacher_id INT NOT NULL REFERENCES teachers(id) ON DELETE RESTRICT,
    subject VARCHAR(150) NOT NULL,             -- Subject name or course code (e.g., 'CS401: Deep Learning')
    period_date DATE NOT NULL,                 -- Date of the scheduled class
    start_time TIME NOT NULL,                  -- Slot start time (e.g., '09:00:00')
    end_time TIME NOT NULL,                    -- Slot end time (e.g., '10:00:00')
    CONSTRAINT chk_period_time_window CHECK (end_time > start_time)
);

-- Indexes for active period resolution during live camera ingestion:
CREATE INDEX IF NOT EXISTS idx_periods_lookup ON periods(classroom_id, period_date, start_time, end_time);
CREATE INDEX IF NOT EXISTS idx_periods_teacher ON periods(teacher_id, period_date);


-- ------------------------------------------------------------------------------
-- 7. Recognition Events Table (Append-Only Raw Audit Log)
-- Why: Every single face detected in any camera frame during a period is logged
-- here immutably for security, anti-spoofing auditing, and post-hoc verification.
-- This table is NEVER updated or deleted.
-- - student_id is NULLABLE: Unknown or unrecognized faces are preserved for review.
-- - is_spoof_flagged: True if MiniFASNet anti-spoofing algorithm flags a print/screen attack.
-- - bounding_box JSONB: Stores [x, y, w, h] coordinates of the face in the camera frame.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recognition_events (
    id BIGSERIAL PRIMARY KEY,
    period_id INT NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    classroom_id INT NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
    student_id INT REFERENCES students(id) ON DELETE SET NULL,  -- NULL if face was unidentified
    confidence_score FLOAT NOT NULL,           -- Cosine similarity match score (0.0 to 1.0)
    is_spoof_flagged BOOLEAN DEFAULT FALSE NOT NULL, -- Anti-spoofing check result (True = spoof attack detected)
    bounding_box JSONB NOT NULL,               -- Bounding box coords {"x": 120, "y": 80, "w": 64, "h": 72}
    frame_timestamp TIMESTAMP WITH TIME ZONE NOT NULL -- Exact time frame was captured from CCTV stream
);

-- Fast lookup index for event timelines per period and student:
CREATE INDEX IF NOT EXISTS idx_rec_events_period_student ON recognition_events(period_id, student_id, frame_timestamp);
CREATE INDEX IF NOT EXISTS idx_rec_events_spoof ON recognition_events(period_id, is_spoof_flagged) WHERE is_spoof_flagged = TRUE;


-- ------------------------------------------------------------------------------
-- 8. Attendance Records Table (Derived Clean State for Dashboard & Reports)
-- Why: The dashboard and Excel reports read from this aggregated state instead
-- of scanning millions of raw recognition_events.
-- - Status tiers:
--   'confirmed'    : High confidence match (score >= CONFIRMED_THRESHOLD) without spoof flag.
--   'needs_review' : Moderate confidence match (NEEDS_REVIEW_THRESHOLD <= score < CONFIRMED_THRESHOLD) 
--                    requiring faculty confirmation on dashboard.
--   'unmarked'     : Temporary state during an ongoing period before conclusive detection.
--   'absent'       : No valid recognition event registered by end of period.
-- - Unique Constraint UNIQUE(student_id, period_id):
--   Guarantees a student has exactly ONE authoritative record per period.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attendance_records (
    id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    period_id INT NOT NULL REFERENCES periods(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL CHECK (status IN ('confirmed', 'needs_review', 'unmarked', 'absent')),
    confidence_score FLOAT,                    -- Highest or representative match confidence
    entry_time TIMESTAMP WITH TIME ZONE,       -- First timestamp student was tracked in classroom
    exit_time TIMESTAMP WITH TIME ZONE,        -- Last timestamp student was tracked in classroom
    marked_by VARCHAR(50) DEFAULT 'system' NOT NULL, -- 'system' (automated CCTV) or 'teacher' (manual override)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_student_period UNIQUE (student_id, period_id)
);

-- Index for live dashboard filtering and monthly report generation
CREATE INDEX IF NOT EXISTS idx_attendance_period_status ON attendance_records(period_id, status);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_id);


-- ------------------------------------------------------------------------------
-- 9. Teacher Overrides Table (Audit Trail)
-- Why: Academic compliance requires an immutable log when a faculty member
-- manually changes a student's attendance (e.g., marked present due to poor lighting
-- or marked absent due to proxy attempt).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teacher_overrides (
    id SERIAL PRIMARY KEY,
    attendance_record_id INT NOT NULL REFERENCES attendance_records(id) ON DELETE CASCADE,
    teacher_id INT NOT NULL REFERENCES teachers(id) ON DELETE RESTRICT,
    previous_status VARCHAR(20) NOT NULL,      -- Status before override ('absent', 'needs_review', etc.)
    new_status VARCHAR(20) NOT NULL CHECK (new_status IN ('confirmed', 'needs_review', 'unmarked', 'absent')),
    reason TEXT NOT NULL,                      -- Required explanation (e.g., 'Student sat in camera blind spot')
    overridden_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index for audit logs lookup per attendance record
CREATE INDEX IF NOT EXISTS idx_overrides_record ON teacher_overrides(attendance_record_id);
CREATE INDEX IF NOT EXISTS idx_overrides_teacher ON teacher_overrides(teacher_id);
