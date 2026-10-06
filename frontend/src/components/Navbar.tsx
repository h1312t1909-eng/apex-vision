import React from 'react';
import { Video, ShieldCheck, Clock, UserCheck, Calendar, FileSpreadsheet, PlusCircle, Download, Camera } from 'lucide-react';
import { Classroom, Period } from '../types';

interface NavbarProps {
  activeTab: 'live' | 'cameras' | 'enrollment' | 'timetable' | 'audit';
  setActiveTab: (tab: 'live' | 'cameras' | 'enrollment' | 'timetable' | 'audit') => void;
  classrooms: Classroom[];
  selectedClassroomId: number | null;
  onSelectClassroom: (id: number) => void;
  activePeriod: Period | null;
  isWsConnected: boolean;
  onOpenEnrollModal: () => void;
  onExportExcel: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  classrooms,
  selectedClassroomId,
  onSelectClassroom,
  activePeriod,
  isWsConnected,
  onOpenEnrollModal,
  onExportExcel
}) => {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      {/* Top Banner: University Brand & Classroom Context */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Institution Name */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-brand-700 flex items-center justify-center text-white shadow-sm">
              <Video className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-brand-700 bg-brand-50 px-2 py-0.5 rounded">
                  Apex University
                </span>
                <span className="text-xs text-slate-400">|</span>
                <span className="text-xs text-slate-500 font-medium">CCTV AI Attendance</span>
              </div>
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">Smart Classroom Attendance</h1>
            </div>
          </div>

          {/* Center: Classroom Selector & Active Lecture Info */}
          <div className="hidden md:flex items-center space-x-4 bg-slate-50 border border-slate-200/80 px-3 py-1.5 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-xs font-medium text-slate-500">Room:</label>
              <select
                className="bg-white border border-slate-200 text-sm font-semibold text-slate-800 rounded px-2.5 py-1 focus:outline-hidden focus:ring-2 focus:ring-brand-500 cursor-pointer"
                value={selectedClassroomId || ''}
                onChange={(e) => onSelectClassroom(Number(e.target.value))}
              >
                {classrooms.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {activePeriod ? (
              <div className="flex items-center space-x-2 border-l border-slate-200 pl-3">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-semibold text-slate-700 truncate max-w-xs">
                  {activePeriod.subject}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  ({activePeriod.start_time.slice(0, 5)} - {activePeriod.end_time.slice(0, 5)})
                </span>
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 border-l border-slate-200 pl-3 text-slate-400 text-xs">
                <Clock className="w-3.5 h-3.5" />
                <span>No active period running</span>
              </div>
            )}
          </div>

          {/* Right: Actions & Stream Status */}
          <div className="flex items-center space-x-2.5">
            {/* Live WebSocket Status Indicator */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                isWsConnected
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isWsConnected ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              <span className="hidden sm:inline">{isWsConnected ? 'Live Stream Active' : 'Connecting...'}</span>
            </div>

            {/* Export Excel Button */}
            <button
              onClick={onExportExcel}
              disabled={!activePeriod}
              title="Download Excel Report"
              className="inline-flex items-center space-x-1 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold px-2.5 py-1.5 rounded-lg shadow-2xs transition-colors disabled:opacity-40 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-emerald-600" />
              <span>Export Excel</span>
            </button>

            {/* Quick Register / Enroll Student Button */}
            <button
              onClick={onOpenEnrollModal}
              className="inline-flex items-center space-x-1.5 bg-brand-700 hover:bg-brand-800 text-white text-xs font-semibold px-3 py-1.5 rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>Enroll Student</span>
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-8 border-t border-slate-100 -mb-px pt-1">
          <button
            onClick={() => setActiveTab('live')}
            className={`flex items-center space-x-2 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
              activeTab === 'live'
                ? 'border-brand-700 text-brand-700 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <UserCheck className="w-4 h-4" />
            <span>Live Attendance Grid</span>
          </button>

          <button
            onClick={() => setActiveTab('cameras')}
            className={`flex items-center space-x-2 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
              activeTab === 'cameras'
                ? 'border-brand-700 text-brand-700 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Camera className="w-4 h-4 text-brand-600" />
            <span>CCTV Camera Feeds (Live Video)</span>
          </button>

          <button
            onClick={() => setActiveTab('timetable')}
            className={`flex items-center space-x-2 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
              activeTab === 'timetable'
                ? 'border-brand-700 text-brand-700 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Calendar className="w-4 h-4" />
            <span>Timetable & Slots</span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`flex items-center space-x-2 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
              activeTab === 'audit'
                ? 'border-brand-700 text-brand-700 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Audit Trail & Anti-Spoof</span>
          </button>
        </nav>
      </div>
    </header>
  );
};
