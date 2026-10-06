export type AttendanceStatus = 'confirmed' | 'needs_review' | 'unmarked' | 'absent';

export interface Student {
  id: number;
  roll_no: string;
  name: string;
  department: string;
  year: number;
  created_at: string;
  embedding_count?: number;
}

export interface Classroom {
  id: number;
  name: string;
  camera_rtsp_url: string;
  location?: string;
}

export interface Period {
  id: number;
  classroom_id: number;
  teacher_id: number;
  subject: string;
  period_date: string;
  start_time: string;
  end_time: string;
  classroom_name?: string;
  teacher_name?: string;
}

export interface AttendanceRecord {
  id: number;
  student_id: number;
  roll_no: string;
  student_name: string;
  department: string;
  period_id: number;
  status: AttendanceStatus;
  confidence_score?: number | null;
  entry_time?: string | null;
  exit_time?: string | null;
  marked_by: 'system' | 'teacher';
  updated_at: string;
}

export interface DashboardStats {
  total_enrolled: number;
  confirmed_count: number;
  needs_review_count: number;
  unmarked_count: number;
  absent_count: number;
  spoof_attempts_blocked: number;
}

export interface RecognitionEvent {
  id: number;
  period_id: number;
  classroom_id: number;
  student_id?: number | null;
  student_name?: string | null;
  roll_no?: string | null;
  confidence_score: number;
  is_spoof_flagged: boolean;
  bounding_box: { x: number; y: number; w: number; h: number };
  frame_timestamp: string;
}

export interface TeacherOverrideLog {
  id: number;
  attendance_record_id: number;
  teacher_id: number;
  teacher_name?: string;
  previous_status: AttendanceStatus;
  new_status: AttendanceStatus;
  reason: string;
  overridden_at: string;
}
