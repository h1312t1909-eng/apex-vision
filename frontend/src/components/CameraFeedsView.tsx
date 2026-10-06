import React, { useState } from 'react';
import { Video, Settings, RefreshCw, Smartphone, Laptop, Radio, Check, AlertCircle } from 'lucide-react';
import { Classroom, Period } from '../types';
import { updateCameraSource } from '../services/api';

interface CameraFeedsViewProps {
  classrooms: Classroom[];
  activePeriod: Period | null;
  onRefreshClassrooms: () => void;
}

export const CameraFeedsView: React.FC<CameraFeedsViewProps> = ({
  classrooms,
  activePeriod,
  onRefreshClassrooms
}) => {
  const [editingRoomId, setEditingRoomId] = useState<number | null>(null);
  const [customSource, setCustomSource] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [message, setMessage] = useState('');

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

  const handleSourceChange = async (classroomId: number, source: string) => {
    try {
      setIsUpdating(true);
      setMessage('');
      await updateCameraSource(classroomId, source);
      setMessage(`Classroom #${classroomId} switched to source: ${source}`);
      setEditingRoomId(null);
      onRefreshClassrooms();
    } catch (err: any) {
      alert(err.message || 'Failed to update camera source');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-brand-700 text-white flex items-center justify-center shadow-xs">
            <Video className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Live CCTV Surveillance Matrix</h2>
            <p className="text-xs text-slate-500">
              Multi-camera video feeds with real-time ArcFace AI bounding boxes & anti-spoof defense
            </p>
          </div>
        </div>

        {message && (
          <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
            {message}
          </span>
        )}
      </div>

      {/* Classroom Cameras Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {classrooms.map((room) => {
          const isLaptopWebcam = room.camera_rtsp_url === '0';
          const isMobileIVCam = room.camera_rtsp_url === '1';

          return (
            <div key={room.id} className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs flex flex-col justify-between">
              {/* Card Header */}
              <div className="p-4 bg-slate-50/80 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold bg-brand-50 text-brand-700 px-2 py-0.5 rounded">
                      Room #{room.id}
                    </span>
                    <h3 className="text-sm font-bold text-slate-900">{room.name}</h3>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">{room.location || 'Campus Academic Block'}</p>
                </div>

                {/* Status Indicator */}
                <div className="flex items-center space-x-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    <span className="w-1.5 h-1.5 mr-1 bg-emerald-500 rounded-full animate-pulse" />
                    LIVE AI STREAM
                  </span>
                  <button
                    onClick={() => {
                      setEditingRoomId(editingRoomId === room.id ? null : room.id);
                      setCustomSource(room.camera_rtsp_url);
                    }}
                    title="Change Camera Input Source"
                    className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 transition-colors"
                  >
                    <Settings className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Source Switcher Panel (Collapsible) */}
              {editingRoomId === room.id && (
                <div className="p-3 bg-brand-50/60 border-b border-brand-100 text-xs space-y-2">
                  <span className="font-bold text-brand-900 block">Select Video Input Source:</span>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => handleSourceChange(room.id, '0')}
                      disabled={isUpdating}
                      className={`py-1.5 px-2 rounded-lg border text-center font-medium flex items-center justify-center space-x-1 transition-all ${
                        room.camera_rtsp_url === '0'
                          ? 'bg-brand-700 text-white border-brand-700 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <Laptop className="w-3 h-3" />
                      <span>Laptop WebCam (0)</span>
                    </button>
                    <button
                      onClick={() => handleSourceChange(room.id, '1')}
                      disabled={isUpdating}
                      className={`py-1.5 px-2 rounded-lg border text-center font-medium flex items-center justify-center space-x-1 transition-all ${
                        room.camera_rtsp_url === '1'
                          ? 'bg-brand-700 text-white border-brand-700 shadow-2xs'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <Smartphone className="w-3 h-3" />
                      <span>Mobile iVCam (1)</span>
                    </button>
                    <button
                      onClick={() => {
                        const url = prompt('Enter RTSP / HTTP Camera URL:', room.camera_rtsp_url);
                        if (url) handleSourceChange(room.id, url);
                      }}
                      disabled={isUpdating}
                      className="py-1.5 px-2 rounded-lg border bg-white text-slate-700 border-slate-200 hover:bg-slate-50 text-center font-medium flex items-center justify-center space-x-1"
                    >
                      <Radio className="w-3 h-3" />
                      <span>Custom RTSP</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Live Video Frame Stream */}
              <div className="relative bg-slate-950 aspect-video flex items-center justify-center overflow-hidden">
                <img
                  src={`${API_BASE}/api/classrooms/${room.id}/video-feed?t=${Date.now()}`}
                  alt={`Live Stream - ${room.name}`}
                  className="w-full h-full object-cover"
                  onError={(e: any) => {
                    // Fallback visual if stream disconnected
                    e.target.style.display = 'none';
                  }}
                />

                {/* CCTV Watermark Overlay */}
                <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-xs px-2.5 py-1 rounded-md text-[11px] font-mono text-white flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                  <span className="font-bold">REC</span>
                  <span>|</span>
                  <span>{room.name}</span>
                </div>

                <div className="absolute bottom-3 right-3 bg-black/60 backdrop-blur-xs px-2.5 py-1 rounded-md text-[10px] font-mono text-emerald-400">
                  Source: {isLaptopWebcam ? 'Laptop Webcam (Index 0)' : isMobileIVCam ? 'iVCam Mobile (Index 1)' : room.camera_rtsp_url}
                </div>
              </div>

              {/* Video Footer Info */}
              <div className="p-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 font-medium">
                <div className="flex items-center space-x-1.5">
                  <Video className="w-3.5 h-3.5 text-brand-600" />
                  <span>ArcFace + MiniFASNet Real-time Ingestion</span>
                </div>
                <span className="text-[11px] text-slate-400 font-mono">2.0 FPS Sampling</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
