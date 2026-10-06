import React, { useEffect, useState } from 'react';
import { ShieldCheck, ShieldAlert, UserCheck, Clock, FileText, Search } from 'lucide-react';
import { RecognitionEvent, TeacherOverrideLog } from '../types';
import { fetchPeriodEvents } from '../services/api';

interface AuditLogViewProps {
  periodId: number | null;
}

export const AuditLogView: React.FC<AuditLogViewProps> = ({ periodId }) => {
  const [events, setEvents] = useState<RecognitionEvent[]>([]);
  const [activeSubTab, setActiveSubTab] = useState<'events' | 'spoofs'>('events');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!periodId) return;
    setIsLoading(true);
    fetchPeriodEvents(periodId, 100)
      .then((data) => setEvents(data))
      .catch((err) => console.error(err))
      .finally(() => setIsLoading(false));
  }, [periodId]);

  const spoofEvents = events.filter((e) => e.is_spoof_flagged);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-700">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-900">Forensic Audit & Anti-Spoofing Records</h3>
            <p className="text-xs text-slate-500">Append-Only Immutable Recognition Log</p>
          </div>
        </div>

        <div className="flex space-x-2">
          <button
            onClick={() => setActiveSubTab('events')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeSubTab === 'events'
                ? 'bg-brand-700 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All Recognitions ({events.length})
          </button>
          <button
            onClick={() => setActiveSubTab('spoofs')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeSubTab === 'spoofs'
                ? 'bg-red-700 text-white'
                : 'bg-red-50 text-red-700 hover:bg-red-100'
            }`}
          >
            Spoof Attacks Blocked ({spoofEvents.length})
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/80 text-slate-600 uppercase text-[10px] tracking-wider font-semibold">
              <th className="py-3 px-4">Timestamp</th>
              <th className="py-3 px-4">Student Identity</th>
              <th className="py-3 px-4">Roll No</th>
              <th className="py-3 px-4">ArcFace Similarity</th>
              <th className="py-3 px-4">Liveness & Anti-Spoof</th>
              <th className="py-3 px-4">Bounding Box (JSONB)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono">
            {isLoading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400 font-sans">
                  Loading forensic records...
                </td>
              </tr>
            ) : (activeSubTab === 'events' ? events : spoofEvents).length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400 font-sans">
                  No recognition events recorded yet.
                </td>
              </tr>
            ) : (
              (activeSubTab === 'events' ? events : spoofEvents).map((evt) => (
                <tr key={evt.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                    {new Date(evt.frame_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 })}
                  </td>
                  <td className="py-3 px-4 font-sans font-bold text-slate-800">
                    {evt.student_name || <span className="text-slate-400 font-normal">Unidentified</span>}
                  </td>
                  <td className="py-3 px-4 text-brand-700 font-semibold">
                    {evt.roll_no || '--'}
                  </td>
                  <td className="py-3 px-4 text-slate-700">
                    {(evt.confidence_score * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-4 font-sans">
                    {evt.is_spoof_flagged ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800 border border-red-200">
                        <ShieldAlert className="w-3 h-3 mr-1 text-red-600" />
                        Spoof Attack
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                        <ShieldCheck className="w-3 h-3 mr-1 text-emerald-600" />
                        Live 3D Skin
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-slate-400 text-[11px]">
                    x:{evt.bounding_box.x}, y:{evt.bounding_box.y}, w:{evt.bounding_box.w}, h:{evt.bounding_box.h}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
