import React from 'react';
import { Calendar, Clock, BookOpen, User, Video } from 'lucide-react';
import { Period } from '../types';

interface TimetableScheduleProps {
  periods: Period[];
  activePeriodId: number | null;
  onSelectPeriod: (periodId: number) => void;
}

export const TimetableSchedule: React.FC<TimetableScheduleProps> = ({
  periods,
  activePeriodId,
  onSelectPeriod
}) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-700">
            <Calendar className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Today's Academic Timetable</h3>
            <p className="text-xs text-slate-500">Scheduled Classroom CCTV Lecture Slots</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {periods.map((p) => {
          const isActive = p.id === activePeriodId;

          return (
            <div
              key={p.id}
              onClick={() => onSelectPeriod(p.id)}
              className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                isActive
                  ? 'bg-brand-50/40 border-brand-300 ring-2 ring-brand-500/20 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-2xs'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-bold bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                    {p.classroom_name || `Classroom #${p.classroom_id}`}
                  </span>
                  {isActive && (
                    <span className="inline-flex items-center text-[10px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                      <span className="w-1.5 h-1.5 mr-1 bg-emerald-500 rounded-full animate-pulse" />
                      Active Slot
                    </span>
                  )}
                </div>

                <h4 className="text-sm font-bold text-slate-900 mb-1">{p.subject}</h4>

                <div className="space-y-1 text-xs text-slate-500 mt-3">
                  <div className="flex items-center space-x-1.5">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    <span>Faculty: {p.teacher_name || 'Assigned Professor'}</span>
                  </div>
                  <div className="flex items-center space-x-1.5 font-mono text-[11px]">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>
                      {p.start_time.slice(0, 5)} - {p.end_time.slice(0, 5)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-semibold text-brand-700">
                <span>View Attendance &rarr;</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
