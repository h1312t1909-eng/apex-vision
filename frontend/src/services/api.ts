/**
 * REST API Client for CCTV Automated Student Attendance System.
 */

import { 
  Classroom, Period, AttendanceRecord, DashboardStats, 
  RecognitionEvent, Student, TeacherOverrideLog 
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function fetchClassrooms(): Promise<Classroom[]> {
  const res = await fetch(`${API_BASE}/api/classrooms`);
  if (!res.ok) throw new Error('Failed to fetch classrooms');
  return res.json();
}

export async function fetchActivePeriod(classroomId: number): Promise<Period | null> {
  const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/active-period`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchPeriods(periodDate?: string, classroomId?: number): Promise<Period[]> {
  const params = new URLSearchParams();
  if (periodDate) params.append('period_date', periodDate);
  if (classroomId) params.append('classroom_id', classroomId.toString());
  
  const res = await fetch(`${API_BASE}/api/periods?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch periods');
  return res.json();
}

export async function fetchPeriodAttendance(periodId: number): Promise<AttendanceRecord[]> {
  const res = await fetch(`${API_BASE}/api/periods/${periodId}/attendance`);
  if (!res.ok) throw new Error('Failed to fetch attendance records');
  return res.json();
}

export async function fetchPeriodStats(periodId: number): Promise<DashboardStats> {
  const res = await fetch(`${API_BASE}/api/periods/${periodId}/stats`);
  if (!res.ok) throw new Error('Failed to fetch period stats');
  return res.json();
}

export async function submitTeacherOverride(
  recordId: number, 
  teacherId: number, 
  newStatus: string, 
  reason: string
): Promise<AttendanceRecord> {
  const res = await fetch(`${API_BASE}/api/attendance/${recordId}/override`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ teacher_id: teacherId, new_status: newStatus, reason })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to submit override');
  }
  return res.json();
}

export async function fetchPeriodEvents(periodId: number, limit = 50): Promise<RecognitionEvent[]> {
  const res = await fetch(`${API_BASE}/api/periods/${periodId}/events?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch recognition events');
  return res.json();
}

export async function fetchStudents(): Promise<Student[]> {
  const res = await fetch(`${API_BASE}/api/students`);
  if (!res.ok) throw new Error('Failed to fetch students');
  return res.json();
}

export async function registerStudent(data: { roll_no: string; name: string; department: string; year: number }): Promise<Student> {
  const res = await fetch(`${API_BASE}/api/students`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to register student');
  }
  return res.json();
}

export async function uploadEnrollmentPhotos(studentId: number, formData: FormData): Promise<any> {
  const res = await fetch(`${API_BASE}/api/students/${studentId}/enroll`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to enroll photos');
  }
  return res.json();
}

export async function finalizePeriod(periodId: number): Promise<{ message: string; unmarked_converted_to_absent: number }> {
  const res = await fetch(`${API_BASE}/api/periods/${periodId}/finalize`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to finalize period');
  return res.json();
}

export async function triggerInstantScan(periodId: number): Promise<any> {
  const res = await fetch(`${API_BASE}/api/periods/${periodId}/scan-now`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Instant scan failed');
  }
  return res.json();
}

export async function updateCameraSource(classroomId: number, cameraRtspUrl: string): Promise<Classroom> {
  const res = await fetch(`${API_BASE}/api/classrooms/${classroomId}/camera-source`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ camera_rtsp_url: cameraRtspUrl })
  });
  if (!res.ok) throw new Error('Failed to update camera source');
  return res.json();
}
