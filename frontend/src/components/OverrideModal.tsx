import React, { useState } from 'react';
import { X, ShieldAlert, Check } from 'lucide-react';
import { AttendanceRecord, AttendanceStatus } from '../types';

interface OverrideModalProps {
  isOpen: boolean;
  onClose: () => void;
  record: AttendanceRecord | null;
  onSubmitOverride: (recordId: number, teacherId: number, newStatus: AttendanceStatus, reason: string) => Promise<void>;
}

export const OverrideModal: React.FC<OverrideModalProps> = ({
  isOpen,
  onClose,
  record,
  onSubmitOverride
}) => {
  const [selectedStatus, setSelectedStatus] = useState<AttendanceStatus>('confirmed');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen || !record) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim() || reason.trim().length < 3) {
      setErrorMsg('Please provide a valid justification reason for academic audit compliance.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg('');
      // Default teacher_id = 1 (Faculty Demo session)
      await onSubmitOverride(record.id, 1, selectedStatus, reason.trim());
      setReason('');
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to submit manual override');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Faculty Manual Override</h3>
              <p className="text-xs text-slate-500">Immutable Academic Audit Log</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Student Summary */}
        <div className="mt-4 p-3 rounded-xl bg-slate-50 border border-slate-200/80">
          <div className="flex justify-between items-start">
            <div>
              <span className="text-xs font-mono font-bold text-brand-700">{record.roll_no}</span>
              <h4 className="text-sm font-bold text-slate-800">{record.student_name}</h4>
              <p className="text-xs text-slate-500">{record.department}</p>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-400 block uppercase">Current State</span>
              <span className="text-xs font-semibold capitalize text-slate-700 font-mono">
                {record.status.replace('_', ' ')}
              </span>
            </div>
          </div>
        </div>

        {/* Override Form */}
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {errorMsg && (
            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              New Attendance State
            </label>
            <div className="grid grid-cols-2 gap-2">
              {(['confirmed', 'needs_review', 'unmarked', 'absent'] as AttendanceStatus[]).map((statusOption) => (
                <button
                  type="button"
                  key={statusOption}
                  onClick={() => setSelectedStatus(statusOption)}
                  className={`py-2 px-3 rounded-lg text-xs font-semibold border text-center transition-all cursor-pointer ${
                    selectedStatus === statusOption
                      ? 'bg-brand-700 text-white border-brand-700 shadow-2xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {statusOption.replace('_', ' ').toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Mandatory Justification Reason <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={3}
              required
              placeholder="e.g. Student sat in camera blind spot, or verified physical presence manually..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full text-xs rounded-lg border border-slate-200 p-2.5 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </div>

          {/* Buttons */}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-end space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold text-white bg-brand-700 hover:bg-brand-800 rounded-lg shadow-2xs transition-colors disabled:opacity-50 cursor-pointer"
            >
              <Check className="w-4 h-4" />
              <span>{isSubmitting ? 'Saving...' : 'Confirm Override'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
