import React from 'react';
import { Check, X, Clock, Edit3, ShieldAlert, ArrowRight } from 'lucide-react';
import { AttendanceRecord } from '../types';

interface StudentCardProps {
  record: AttendanceRecord;
  onQuickApprove: (record: AttendanceRecord) => void;
  onQuickReject: (record: AttendanceRecord) => void;
  onOpenOverride: (record: AttendanceRecord) => void;
}

export const StudentCard: React.FC<StudentCardProps> = ({
  record,
  onQuickApprove,
  onQuickReject,
  onOpenOverride
}) => {
  const getStatusBadge = () => {
    switch (record.status) {
      case 'confirmed':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-600" />
            Confirmed
          </span>
        );
      case 'needs_review':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200 animate-pulse">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-amber-600" />
            Needs Review
          </span>
        );
      case 'absent':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-rose-600" />
            Absent
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-slate-400" />
            Unmarked
          </span>
        );
    }
  };

  const formatTime = (isoString?: string | null) => {
    if (!isoString) return '--:--';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '--:--';
    }
  };

  const confidencePct = Math.round((record.confidence_score || 0) * 100);

  return (
    <div
      className={`bg-white rounded-xl border p-4 shadow-2xs hover:shadow-sm transition-all flex flex-col justify-between ${
        record.status === 'needs_review'
          ? 'border-amber-300 ring-1 ring-amber-200 bg-amber-50/10'
          : 'border-slate-200/90'
      }`}
    >
      {/* Card Header: Student Info & Status */}
      <div>
        <div className="flex items-start justify-between mb-2">
          <div>
            <span className="text-[11px] font-mono font-bold tracking-wider text-brand-700 bg-brand-50 px-1.5 py-0.5 rounded">
              {record.roll_no}
            </span>
            <h3 className="text-sm font-bold text-slate-900 mt-1 leading-snug">
              {record.student_name}
            </h3>
            <p className="text-xs text-slate-500">{record.department}</p>
          </div>
          {getStatusBadge()}
        </div>

        {/* Confidence Progress Bar */}
        {record.confidence_score !== null && record.confidence_score !== undefined && record.confidence_score > 0 && (
          <div className="mt-2 mb-3">
            <div className="flex justify-between text-[11px] font-medium text-slate-500 mb-1">
              <span>Match Confidence</span>
              <span className="font-semibold text-slate-700 font-mono">{confidencePct}%</span>
            </div>
            <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  confidencePct >= 68
                    ? 'bg-emerald-500'
                    : confidencePct >= 50
                    ? 'bg-amber-500'
                    : 'bg-slate-400'
                }`}
                style={{ width: `${Math.min(100, Math.max(0, confidencePct))}%` }}
              />
            </div>
          </div>
        )}

        {/* Timestamps: Entry & Exit times from Centroid Tracker */}
        <div className="grid grid-cols-2 gap-2 mt-3 pt-2.5 border-t border-slate-100 text-[11px]">
          <div>
            <span className="text-slate-400 block">Entry Time</span>
            <span className="font-medium text-slate-700 font-mono">
              {formatTime(record.entry_time)}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block">Exit / Last Seen</span>
            <span className="font-medium text-slate-700 font-mono">
              {formatTime(record.exit_time)}
            </span>
          </div>
        </div>

        {/* Marked By Attribution */}
        <div className="mt-2 flex items-center justify-between text-[10px] text-slate-400">
          <span>Source:</span>
          <span className="font-semibold uppercase tracking-wider text-slate-600">
            {record.marked_by === 'teacher' ? 'Faculty Override' : 'CCTV ArcFace AI'}
          </span>
        </div>
      </div>

      {/* Action Footer: Quick One-Click Faculty Approvals */}
      <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
        {record.status === 'needs_review' ? (
          <div className="flex items-center space-x-1.5 w-full">
            <button
              onClick={() => onQuickApprove(record)}
              className="flex-1 inline-flex items-center justify-center space-x-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold py-1.5 px-2 rounded-md shadow-2xs transition-colors cursor-pointer"
              title="Quick Approve as Present"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Confirm</span>
            </button>
            <button
              onClick={() => onQuickReject(record)}
              className="flex-1 inline-flex items-center justify-center space-x-1 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold py-1.5 px-2 rounded-md shadow-2xs transition-colors cursor-pointer"
              title="Quick Mark as Absent"
            >
              <X className="w-3.5 h-3.5" />
              <span>Reject</span>
            </button>
          </div>
        ) : (
          <button
            onClick={() => onOpenOverride(record)}
            className="w-full inline-flex items-center justify-center space-x-1.5 text-xs font-medium text-slate-600 hover:text-brand-700 hover:bg-slate-50 py-1.5 px-2 rounded border border-slate-200 transition-colors cursor-pointer"
          >
            <Edit3 className="w-3.5 h-3.5 text-slate-400" />
            <span>Manual Override</span>
          </button>
        )}
      </div>
    </div>
  );
};
