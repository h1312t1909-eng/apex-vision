import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/Navbar';
import { StatCards } from './components/StatCards';
import { AttendanceGrid } from './components/AttendanceGrid';
import { LiveActivityFeed } from './components/LiveActivityFeed';
import { OverrideModal } from './components/OverrideModal';
import { EnrollmentModal } from './components/EnrollmentModal';
import { TimetableSchedule } from './components/TimetableSchedule';
import { AuditLogView } from './components/AuditLogView';
import { CameraFeedsView } from './components/CameraFeedsView';

import { 
  Classroom, Period, AttendanceRecord, DashboardStats, AttendanceStatus 
} from './types';
import { 
  fetchClassrooms, fetchPeriods, fetchActivePeriod, 
  fetchPeriodAttendance, fetchPeriodStats, submitTeacherOverride,
  triggerInstantScan
} from './services/api';
import { useClassroomWebSocket, WebSocketEvent } from './hooks/useWebSocket';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'live' | 'cameras' | 'enrollment' | 'timetable' | 'audit'>('live');
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [selectedClassroomId, setSelectedClassroomId] = useState<number | null>(null);
  const [activePeriod, setActivePeriod] = useState<Period | null>(null);
  const [allPeriods, setAllPeriods] = useState<Period[]>([]);
  
  // Attendance and stats state
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [isScanning, setIsScanning] = useState(false);
  
  // Real-time live feed events
  const [liveEvents, setLiveEvents] = useState<WebSocketEvent[]>([]);

  // Modals state
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false);
  const [isOverrideModalOpen, setIsOverrideModalOpen] = useState(false);
  const [selectedRecordForOverride, setSelectedRecordForOverride] = useState<AttendanceRecord | null>(null);

  // Load classrooms on boot
  const loadClassrooms = useCallback(async () => {
    try {
      const data = await fetchClassrooms();
      setClassrooms(data);
      if (data.length > 0 && selectedClassroomId === null) {
        setSelectedClassroomId(data[0].id);
      }
    } catch (err) {
      console.error('[Error fetching classrooms]', err);
    }
  }, [selectedClassroomId]);

  useEffect(() => {
    loadClassrooms();
    fetchPeriods()
      .then((data) => setAllPeriods(data))
      .catch((err) => console.error('[Error fetching periods]', err));
  }, [loadClassrooms]);

  // Fetch active period & attendance whenever selected classroom changes
  const loadPeriodData = useCallback(async (classroomId: number) => {
    try {
      const active = await fetchActivePeriod(classroomId);
      setActivePeriod(active);

      if (active) {
        const [attData, statsData] = await Promise.all([
          fetchPeriodAttendance(active.id),
          fetchPeriodStats(active.id)
        ]);
        setRecords(attData);
        setStats(statsData);
      } else {
        // Fallback to latest period for this classroom
        const periods = await fetchPeriods(undefined, classroomId);
        if (periods.length > 0) {
          const latest = periods[0];
          setActivePeriod(latest);
          const [attData, statsData] = await Promise.all([
            fetchPeriodAttendance(latest.id),
            fetchPeriodStats(latest.id)
          ]);
          setRecords(attData);
          setStats(statsData);
        } else {
          setRecords([]);
          setStats(null);
        }
      }
    } catch (err) {
      console.error('[Error loading period data]', err);
    }
  }, []);

  useEffect(() => {
    if (selectedClassroomId) {
      loadPeriodData(selectedClassroomId);
    }
  }, [selectedClassroomId, loadPeriodData]);

  // WebSocket event handler for real-time live push
  const handleWebSocketMessage = useCallback((event: WebSocketEvent) => {
    setLiveEvents((prev) => [event, ...prev.slice(0, 49)]);

    if (event.event_type === 'attendance_update') {
      const updated = event.data;
      setRecords((prev) => {
        const idx = prev.findIndex((r) => r.student_id === updated.student_id);
        if (idx !== -1) {
          const next = [...prev];
          next[idx] = {
            ...next[idx],
            status: updated.status,
            confidence_score: updated.confidence_score ?? next[idx].confidence_score,
            entry_time: updated.entry_time ?? next[idx].entry_time,
            exit_time: updated.exit_time ?? next[idx].exit_time,
            marked_by: updated.marked_by ?? next[idx].marked_by,
            updated_at: event.timestamp
          };
          return next;
        } else {
          if (selectedClassroomId) loadPeriodData(selectedClassroomId);
        }
        return prev;
      });

      if (activePeriod) {
        fetchPeriodStats(activePeriod.id).then(setStats).catch(console.error);
      }
    }
  }, [activePeriod, selectedClassroomId, loadPeriodData]);

  const { isConnected: isWsConnected } = useClassroomWebSocket(
    selectedClassroomId,
    handleWebSocketMessage
  );

  // Faculty Quick Actions
  const handleQuickApprove = async (record: AttendanceRecord) => {
    try {
      await submitTeacherOverride(record.id, 1, 'confirmed', 'Faculty quick confirmation from live dashboard');
      if (selectedClassroomId) loadPeriodData(selectedClassroomId);
    } catch (err) {
      console.error(err);
    }
  };

  const handleQuickReject = async (record: AttendanceRecord) => {
    try {
      await submitTeacherOverride(record.id, 1, 'absent', 'Faculty manual absent override');
      if (selectedClassroomId) loadPeriodData(selectedClassroomId);
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenOverride = (record: AttendanceRecord) => {
    setSelectedRecordForOverride(record);
    setIsOverrideModalOpen(true);
  };

  const handleSubmitOverride = async (recordId: number, teacherId: number, newStatus: AttendanceStatus, reason: string) => {
    await submitTeacherOverride(recordId, teacherId, newStatus, reason);
    if (selectedClassroomId) {
      await loadPeriodData(selectedClassroomId);
    }
  };

  const handleExportExcel = () => {
    if (!activePeriod) return;
    const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
    window.open(`${API_BASE}/api/reports/period/${activePeriod.id}/excel`, '_blank');
  };

  const handleTriggerScan = async () => {
    if (!activePeriod) return;
    try {
      setIsScanning(true);
      await triggerInstantScan(activePeriod.id);
      if (selectedClassroomId) {
        await loadPeriodData(selectedClassroomId);
      }
    } catch (err: any) {
      alert(err.message || 'Scan error');
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Navbar with Academic Branding */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        classrooms={classrooms}
        selectedClassroomId={selectedClassroomId}
        onSelectClassroom={(id) => setSelectedClassroomId(id)}
        activePeriod={activePeriod}
        isWsConnected={isWsConnected}
        onOpenEnrollModal={() => setIsEnrollModalOpen(true)}
        onExportExcel={handleExportExcel}
      />

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full">
        {/* Tab 1: Live Attendance Grid */}
        {activeTab === 'live' && (
          <div>
            <StatCards stats={stats} onFilterSelect={(f) => setActiveFilter(f)} />

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
              <div className="lg:col-span-3">
                <AttendanceGrid
                  records={records}
                  onQuickApprove={handleQuickApprove}
                  onQuickReject={handleQuickReject}
                  onOpenOverride={handleOpenOverride}
                  onRefresh={() => selectedClassroomId && loadPeriodData(selectedClassroomId)}
                  onTriggerScan={handleTriggerScan}
                  isScanning={isScanning}
                  activeFilter={activeFilter}
                  setActiveFilter={setActiveFilter}
                />
              </div>

              <div className="lg:col-span-1 sticky top-24">
                <LiveActivityFeed events={liveEvents} />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Live CCTV Camera Feeds Matrix */}
        {activeTab === 'cameras' && (
          <CameraFeedsView
            classrooms={classrooms}
            activePeriod={activePeriod}
            onRefreshClassrooms={loadClassrooms}
          />
        )}

        {/* Tab 3: Timetable & Lecture Slots */}
        {activeTab === 'timetable' && (
          <TimetableSchedule
            periods={allPeriods}
            activePeriodId={activePeriod?.id || null}
            onSelectPeriod={(periodId) => {
              const p = allPeriods.find((x) => x.id === periodId);
              if (p) {
                setSelectedClassroomId(p.classroom_id);
                setActiveTab('live');
              }
            }}
          />
        )}

        {/* Tab 4: Audit Trail & Forensic Records */}
        {activeTab === 'audit' && (
          <AuditLogView periodId={activePeriod?.id || null} />
        )}
      </main>

      {/* Override Modal */}
      <OverrideModal
        isOpen={isOverrideModalOpen}
        onClose={() => {
          setIsOverrideModalOpen(false);
          setSelectedRecordForOverride(null);
        }}
        record={selectedRecordForOverride}
        onSubmitOverride={handleSubmitOverride}
      />

      {/* Student Enrollment Modal */}
      <EnrollmentModal
        isOpen={isEnrollModalOpen}
        onClose={() => setIsEnrollModalOpen(false)}
        onSuccess={() => {
          if (selectedClassroomId) loadPeriodData(selectedClassroomId);
        }}
      />
    </div>
  );
};
