import React from 'react';
import { Activity, ShieldAlert, CheckCircle2, UserCheck, AlertTriangle } from 'lucide-react';
import { WebSocketEvent } from '../hooks/useWebSocket';

interface LiveActivityFeedProps {
  events: WebSocketEvent[];
}

export const LiveActivityFeed: React.FC<LiveActivityFeedProps> = ({ events }) => {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col h-[520px]">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-brand-600 animate-pulse" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            Real-Time CCTV Stream Feed
          </h3>
        </div>
        <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono font-medium">
          {events.length} events
        </span>
      </div>

      {/* Events Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pt-3 pr-1">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 p-4">
            <Activity className="w-8 h-8 text-slate-300 mb-2" />
            <p className="text-xs font-medium">Listening for CCTV recognitions...</p>
            <p className="text-[10px] text-slate-400 mt-0.5">
              Live detections and anti-spoof checks will stream here in real time.
            </p>
          </div>
        ) : (
          events.map((evt, idx) => {
            const isSpoof = evt.event_type === 'spoof_alert' || evt.data?.is_spoof;
            const isAttendance = evt.event_type === 'attendance_update';
            const timeStr = new Date(evt.timestamp).toLocaleTimeString();

            return (
              <div
                key={idx}
                className={`p-2.5 rounded-lg border text-xs transition-all ${
                  isSpoof
                    ? 'bg-red-50/80 border-red-200 text-red-900'
                    : isAttendance
                    ? 'bg-emerald-50/60 border-emerald-200 text-slate-800'
                    : 'bg-slate-50 border-slate-200/80 text-slate-800'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center space-x-1.5">
                    {isSpoof ? (
                      <ShieldAlert className="w-3.5 h-3.5 text-red-600 shrink-0" />
                    ) : isAttendance ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    ) : (
                      <UserCheck className="w-3.5 h-3.5 text-brand-600 shrink-0" />
                    )}
                    <span className="font-bold text-[11px]">
                      {isSpoof
                        ? 'SPOOF ATTACK BLOCKED'
                        : isAttendance
                        ? 'ATTENDANCE LOGGED'
                        : 'FACE DETECTED'}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{timeStr}</span>
                </div>

                <div className="pl-5 space-y-0.5">
                  {isSpoof ? (
                    <p className="text-[11px] font-semibold text-red-700">
                      MiniFASNet flagged non-human liveness (Score: {(evt.data?.liveness_score || 0).toFixed(2)})
                    </p>
                  ) : (
                    <>
                      <p className="text-[11px] font-semibold text-slate-800">
                        {evt.data?.student_name || 'Unidentified Face'}{' '}
                        {evt.data?.roll_no && (
                          <span className="font-mono text-brand-700 font-normal">({evt.data.roll_no})</span>
                        )}
                      </p>
                      {evt.data?.confidence_score !== undefined && (
                        <p className="text-[10px] text-slate-500 font-mono">
                          Cosine Match: {(evt.data.confidence_score * 100).toFixed(1)}% | Status: {evt.data.status_tier || evt.data.status}
                        </p>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
