import React, { useState } from 'react';
import { 
  X, UploadCloud, UserPlus, CheckCircle, AlertCircle, Camera, 
  Trash2, Video, Sparkles
} from 'lucide-react';
import { registerStudent, uploadEnrollmentPhotos } from '../services/api';

interface EnrollmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface CapturedPhoto {
  file: File;
  previewUrl: string;
  angle: string;
  lighting: string;
}

export const EnrollmentModal: React.FC<EnrollmentModalProps> = ({
  isOpen,
  onClose,
  onSuccess
}) => {
  const [step, setStep] = useState<1 | 2>(1); // 1: Details, 2: Photos
  const [rollNo, setRollNo] = useState('');
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('Computer Science');
  const [year, setYear] = useState(3);
  const [studentId, setStudentId] = useState<number | null>(null);

  // Capture mode: 'cctv' (Active CCTV/iVCam Stream) or 'upload' (File upload)
  const [captureMode, setCaptureMode] = useState<'cctv' | 'upload'>('cctv');
  const [capturedPhotos, setCapturedPhotos] = useState<CapturedPhoto[]>([]);
  const [currentAngleIdx, setCurrentAngleIdx] = useState(0);
  const [isCapturing, setIsCapturing] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [enrollmentResult, setEnrollmentResult] = useState<any | null>(null);

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

  const anglePrompts = [
    { label: 'frontal', title: 'Look Directly at Camera (Frontal)', tip: 'Keep head straight and neutral' },
    { label: 'profile_left', title: 'Turn Head Slightly Left (~30°)', tip: 'Angle head toward your left' },
    { label: 'profile_right', title: 'Turn Head Slightly Right (~30°)', tip: 'Angle head toward your right' },
    { label: 'tilted_up', title: 'Tilt Head Slightly Upward', tip: 'Simulates high-wall CCTV angle' },
    { label: 'tilted_down', title: 'Tilt Head Slightly Downward', tip: 'Looking down toward desk' },
    { label: 'expression_smile', title: 'Natural Smile / Expression', tip: 'Helps ArcFace intra-class variance' },
  ];

  if (!isOpen) return null;

  const handleCreateStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      setErrorMsg('');
      const student = await registerStudent({
        roll_no: rollNo.trim().toUpperCase(),
        name: name.trim(),
        department,
        year: Number(year)
      });
      setStudentId(student.id);
      setStep(2);
    } catch (err: any) {
      setErrorMsg(err.message || 'Registration failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const captureFromCCTV = async () => {
    try {
      setIsCapturing(true);
      setErrorMsg('');

      // Fetch snapshot directly from active camera worker
      const res = await fetch(`${API_BASE}/api/classrooms/1/snapshot?t=${Date.now()}`);
      if (!res.ok) {
        throw new Error('Could not grab frame from camera stream. Ensure camera/iVCam is active.');
      }
      const blob = await res.blob();
      const angleInfo = anglePrompts[currentAngleIdx % anglePrompts.length];
      const filename = `enroll_${rollNo}_${angleInfo.label}_${Date.now()}.jpg`;
      const file = new File([blob], filename, { type: 'image/jpeg' });
      const previewUrl = URL.createObjectURL(blob);

      setCapturedPhotos((prev) => [
        ...prev,
        {
          file,
          previewUrl,
          angle: angleInfo.label,
          lighting: 'normal'
        }
      ]);

      setCurrentAngleIdx((prev) => prev + 1);
    } catch (err: any) {
      setErrorMsg(err.message || 'Capture failed');
    } finally {
      setIsCapturing(false);
    }
  };

  const removePhoto = (index: number) => {
    setCapturedPhotos((prev) => {
      const next = [...prev];
      URL.revokeObjectURL(next[index].previewUrl);
      next.splice(index, 1);
      return next;
    });
  };

  const handleSubmitEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || capturedPhotos.length === 0) {
      setErrorMsg('Please capture or select at least 3-6 reference photos.');
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg('');

      const formData = new FormData();
      capturedPhotos.forEach((item) => {
        formData.append('photos', item.file);
        formData.append('angles', item.angle);
        formData.append('lighting', item.lighting);
      });

      const res = await uploadEnrollmentPhotos(studentId, formData);
      setEnrollmentResult(res);
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || 'Enrollment failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files);
    const standardAngles = ['frontal', 'profile_left', 'profile_right', 'tilted_up', 'tilted_down', 'expression_smile'];

    const newPhotos: CapturedPhoto[] = files.map((file, idx) => ({
      file,
      previewUrl: URL.createObjectURL(file),
      angle: standardAngles[idx % standardAngles.length],
      lighting: 'normal'
    }));

    setCapturedPhotos((prev) => [...prev, ...newPhotos]);
  };

  const resetForm = () => {
    setStep(1);
    setRollNo('');
    setName('');
    setStudentId(null);
    setCapturedPhotos([]);
    setCurrentAngleIdx(0);
    setErrorMsg('');
    setEnrollmentResult(null);
  };

  const currentPrompt = anglePrompts[currentAngleIdx % anglePrompts.length];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center text-brand-700">
              <UserPlus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Student Enrollment Flow</h3>
              <p className="text-xs text-slate-500">
                Step {step} of 2: {step === 1 ? 'Academic Record' : 'Live Camera Reference Ingestion'}
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              resetForm();
              onClose();
            }}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center space-x-1.5">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Step 1: Student Details */}
        {step === 1 && (
          <form onSubmit={handleCreateStudent} className="mt-4 space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                College Roll Number <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. 2026CS101"
                value={rollNo}
                onChange={(e) => setRollNo(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-200 p-2.5 uppercase font-mono font-bold text-slate-800 focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Full Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Alexander Hamilton"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-200 p-2.5 text-slate-800 focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Department</label>
                <select
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full text-xs rounded-lg border border-slate-200 p-2.5 text-slate-800 focus:ring-2 focus:ring-brand-500 bg-white"
                >
                  <option value="Computer Science">Computer Science</option>
                  <option value="Information Technology">Information Technology</option>
                  <option value="Electronics & Comm">Electronics & Comm</option>
                  <option value="Mechanical Engineering">Mechanical Engineering</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Academic Year</label>
                <select
                  value={year}
                  onChange={(e) => setYear(Number(e.target.value))}
                  className="w-full text-xs rounded-lg border border-slate-200 p-2.5 text-slate-800 focus:ring-2 focus:ring-brand-500 bg-white"
                >
                  <option value={1}>1st Year</option>
                  <option value={2}>2nd Year</option>
                  <option value={3}>3rd Year</option>
                  <option value={4}>4th Year</option>
                </select>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end space-x-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 text-xs font-semibold text-white bg-brand-700 hover:bg-brand-800 rounded-lg shadow-2xs cursor-pointer"
              >
                Next: Face Capture &rarr;
              </button>
            </div>
          </form>
        )}

        {/* Step 2: Live Camera & Photo Ingestion */}
        {step === 2 && !enrollmentResult && (
          <div className="mt-4 space-y-4">
            {/* Mode Switcher: Active CCTV Stream vs Upload */}
            <div className="flex bg-slate-100 p-1 rounded-lg">
              <button
                type="button"
                onClick={() => setCaptureMode('cctv')}
                className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  captureMode === 'cctv'
                    ? 'bg-white text-brand-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Video className="w-3.5 h-3.5" />
                <span>Live Camera / iVCam Stream</span>
              </button>
              <button
                type="button"
                onClick={() => setCaptureMode('upload')}
                className={`flex-1 flex items-center justify-center space-x-1.5 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  captureMode === 'upload'
                    ? 'bg-white text-brand-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Upload Photo Files</span>
              </button>
            </div>

            {/* Mode A: Active CCTV Live Video Feed */}
            {captureMode === 'cctv' && (
              <div className="space-y-3">
                {/* Angle Prompt Guide Banner */}
                <div className="bg-brand-50 border border-brand-200/80 p-2.5 rounded-xl flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-brand-900 block">
                      📸 Prompt #{((currentAngleIdx % anglePrompts.length) + 1)}: {currentPrompt.title}
                    </span>
                    <span className="text-[11px] text-slate-500">{currentPrompt.tip}</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold bg-brand-200/70 text-brand-800 px-2 py-0.5 rounded-full">
                    {capturedPhotos.length} / 6 Captured
                  </span>
                </div>

                {/* Video Feed Window using backend MJPEG Stream (No browser lock conflict!) */}
                <div className="relative bg-slate-900 rounded-xl overflow-hidden aspect-video flex items-center justify-center shadow-inner">
                  <img
                    src={`${API_BASE}/api/classrooms/1/video-feed`}
                    alt="Active Camera Preview"
                    className="w-full h-full object-cover"
                  />

                  {/* Face Alignment Oval Target Overlay */}
                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="w-36 h-48 border-2 border-dashed border-white/70 rounded-[50%] flex items-center justify-center">
                      <span className="text-[10px] text-white/90 bg-black/50 px-2 py-0.5 rounded backdrop-blur-xs">
                        Align Face in Oval
                      </span>
                    </div>
                  </div>
                </div>

                {/* Capture Snapshot Button */}
                <button
                  type="button"
                  onClick={captureFromCCTV}
                  disabled={isCapturing}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-xl shadow-xs transition-all flex items-center justify-center space-x-2 disabled:opacity-50 cursor-pointer active:scale-[0.99]"
                >
                  <Camera className="w-4 h-4" />
                  <span>{isCapturing ? 'Grabbing Frame...' : `📸 Capture Snapshot for "${currentPrompt.label}"`}</span>
                </button>
              </div>
            )}

            {/* Mode B: File Upload */}
            {captureMode === 'upload' && (
              <div className="border border-dashed border-slate-300 rounded-xl p-5 text-center bg-slate-50/50">
                <UploadCloud className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <label className="text-xs font-semibold text-brand-700 cursor-pointer hover:underline block">
                  Click to select 4-8 face photos from your computer
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
                <p className="text-[10px] text-slate-400 mt-1">JPEG, PNG supported (multiple angles recommended)</p>
              </div>
            )}

            {/* Captured Photos Gallery */}
            {capturedPhotos.length > 0 && (
              <div>
                <span className="text-xs font-semibold text-slate-700 block mb-1.5">
                  Captured Reference Embeddings ({capturedPhotos.length})
                </span>
                <div className="flex space-x-2 overflow-x-auto pb-2">
                  {capturedPhotos.map((photo, i) => (
                    <div key={i} className="relative group shrink-0 w-16 h-20 rounded-lg overflow-hidden border border-slate-200 shadow-2xs">
                      <img src={photo.previewUrl} alt={photo.angle} className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <button
                          type="button"
                          onClick={() => removePhoto(i)}
                          className="p-1 rounded-full bg-rose-600 text-white hover:bg-rose-700"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <span className="absolute bottom-0 inset-x-0 bg-black/60 text-[8px] text-white text-center py-0.5 truncate px-0.5">
                        {photo.angle}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Footer Buttons */}
            <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-xs text-slate-500 hover:text-slate-700 font-medium"
              >
                &larr; Back
              </button>

              <button
                type="button"
                onClick={handleSubmitEnrollment}
                disabled={isSubmitting || capturedPhotos.length === 0}
                className="px-4 py-2 text-xs font-semibold text-white bg-brand-700 hover:bg-brand-800 rounded-lg shadow-2xs transition-colors disabled:opacity-50 cursor-pointer"
              >
                {isSubmitting ? 'Computing ArcFace Embeddings...' : `Submit ${capturedPhotos.length} Reference Photo(s)`}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Result Breakdown */}
        {enrollmentResult && (
          <div className="mt-4 space-y-4">
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center">
              <CheckCircle className="w-8 h-8 text-emerald-600 mx-auto mb-1.5" />
              <h4 className="text-sm font-bold text-emerald-900">Enrollment Complete!</h4>
              <p className="text-xs text-emerald-700 mt-0.5">
                Successfully stored {enrollmentResult.successful_enrollments} reference face vectors in PostgreSQL pgvector.
              </p>
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1 text-xs">
              {enrollmentResult.details?.map((d: any, idx: number) => (
                <div
                  key={idx}
                  className={`p-2 rounded border flex justify-between items-center text-[11px] ${
                    d.success ? 'bg-slate-50 border-slate-200' : 'bg-rose-50 border-rose-200 text-rose-800'
                  }`}
                >
                  <span className="capitalize font-medium">Angle: {d.angle}</span>
                  <span>{d.success ? '✓ 512-dim Vector Enrolled' : `✗ ${d.error}`}</span>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => {
                  resetForm();
                  onClose();
                }}
                className="px-4 py-2 text-xs font-semibold text-white bg-brand-700 hover:bg-brand-800 rounded-lg shadow-2xs cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
