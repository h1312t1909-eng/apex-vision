import React, { useState } from 'react';
import { Search, Filter, RefreshCw, CheckCircle2, Camera } from 'lucide-react';
import { AttendanceRecord } from '../types';
import { StudentCard } from './StudentCard';

interface AttendanceGridProps {
  records: AttendanceRecord[];
  onQuickApprove: (record: AttendanceRecord) => void;
  onQuickReject: (record: AttendanceRecord) => void;
  onOpenOverride: (record: AttendanceRecord) => void;
  onRefresh: () => void;
  onTriggerScan?: () => void;
  isScanning?: boolean;
  activeFilter: string;
  setActiveFilter: (filter: string) => void;
}

export const AttendanceGrid: React.FC<AttendanceGridProps> = ({
  records,
  onQuickApprove,
  onQuickReject,
  onOpenOverride,
  onRefresh,
  onTriggerScan,
  isScanning = false,
  activeFilter,
  setActiveFilter
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Filter records by search query and active tab
  const filteredRecords = records.filter((rec) => {
    const matchesSearch =
      rec.student_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rec.roll_no.toLowerCase().includes(searchQuery.toLowerCase());

    if (!matchesSearch) return false;

    if (activeFilter === 'confirmed') return rec.status === 'confirmed';
    if (activeFilter === 'needs_review') return rec.status === 'needs_review';
    if (activeFilter === 'unmarked') return rec.status === 'unmarked';
    if (activeFilter === 'absent') return rec.status === 'absent';
    return true; // 'all'
  });

  const filterTabs = [
    { id: 'all', label: 'All Students', count: records.length },
    { id: 'confirmed', label: 'Confirmed', count: records.filter((r) => r.status === 'confirmed').length },
    { id: 'needs_review', label: 'Needs Review', count: records.filter((r) => r.status === 'needs_review').length },
    { id: 'unmarked', label: 'Unmarked', count: records.filter((r) => r.status === 'unmarked').length },
    { id: 'absent', label: 'Absent', count: records.filter((r) => r.status === 'absent').length },
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
      {/* Grid Controls Header: Search & Filter Tabs */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pb-4 border-b border-slate-100">
        {/* Filter Pills */}
        <div className="flex items-center space-x-1.5 overflow-x-auto w-full sm:w-auto pb-2 sm:pb-0">
          {filterTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                activeFilter === tab.id
                  ? 'bg-brand-700 text-white shadow-2xs'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200/70'
              }`}
            >
              {tab.label}{' '}
              <span
                className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full ${
                  activeFilter === tab.id ? 'bg-brand-800 text-white' : 'bg-white text-slate-700'
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search Bar, Scan Now Button & Refresh Button */}
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          {onTriggerScan && (
            <button
              onClick={onTriggerScan}
              disabled={isScanning}
              title="Instant Scan Face from Camera"
              className="inline-flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold px-3 py-2 rounded-lg shadow-2xs transition-all disabled:opacity-50 cursor-pointer shrink-0 active:scale-95"
            >
              <Camera className="w-3.5 h-3.5" />
              <span>{isScanning ? 'Scanning...' : 'Scan Camera Now'}</span>
            </button>
          )}

          <div className="relative w-full sm:w-56">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search Roll No/Name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 text-xs rounded-lg pl-9 pr-3 py-2 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-brand-500 focus:bg-white"
            />
          </div>

          <button
            onClick={onRefresh}
            title="Refresh Roster"
            className="p-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer shrink-0"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Student Cards Grid */}
      {filteredRecords.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-5">
          {filteredRecords.map((record) => (
            <StudentCard
              key={record.id}
              record={record}
              onQuickApprove={onQuickApprove}
              onQuickReject={onQuickReject}
              onOpenOverride={onOpenOverride}
            />
          ))}
        </div>
      ) : (
        <div className="py-16 text-center">
          <CheckCircle2 className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-700">No student records found</h4>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
            {searchQuery
              ? `No students matching "${searchQuery}" in this filter.`
              : 'Attendance roster is empty for this period.'}
          </p>
        </div>
      )}
    </div>
  );
};
