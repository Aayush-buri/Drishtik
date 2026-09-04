import React, { useState, useRef } from 'react';
import { 
  X, Scissors, Crop as CropIcon, Film, Play, Pause, 
  RotateCcw, ShieldCheck, AlertCircle, Loader2 
} from 'lucide-react';
import type { Evidence, DeriveEvidenceRequest } from '../../../services/evidenceService';
import { evidenceService } from '../../../services/evidenceService';

interface CreateDerivedClipModalProps {
  isOpen: boolean;
  onClose: () => void;
  evidence: Evidence;
  caseIdentifier: string;
  onDerivedCreated: (derived: Evidence) => void;
}

export function CreateDerivedClipModal({
  isOpen,
  onClose,
  evidence,
  caseIdentifier,
  onDerivedCreated
}: CreateDerivedClipModalProps) {
  const [operation, setOperation] = useState<'TRIM' | 'CROP' | 'TRIM_AND_CROP'>('TRIM');
  
  // Video reference & playback state
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [videoWidth, setVideoWidth] = useState(1920);
  const [videoHeight, setVideoHeight] = useState(1080);

  // Trim state
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(10);

  // Crop state in actual video pixels
  const [crop, setCrop] = useState({ x: 0, y: 0, width: 1280, height: 720 });

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize bounds when metadata loads
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration || 10;
      const vw = videoRef.current.videoWidth || 1920;
      const vh = videoRef.current.videoHeight || 1080;
      setDuration(dur);
      setStartTime(0);
      setEndTime(Math.min(dur, Math.max(1, Math.round(dur))));
      setVideoWidth(vw);
      setVideoHeight(vh);
      setCrop({
        x: Math.round(vw * 0.1),
        y: Math.round(vh * 0.1),
        width: Math.round(vw * 0.8),
        height: Math.round(vh * 0.8)
      });
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      // Loop or stop if past end in preview
      if (operation !== 'CROP' && videoRef.current.currentTime >= endTime) {
        videoRef.current.pause();
        setIsPlaying(false);
        videoRef.current.currentTime = startTime;
      }
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        if (operation !== 'CROP' && (videoRef.current.currentTime < startTime || videoRef.current.currentTime >= endTime)) {
          videoRef.current.currentTime = startTime;
        }
        videoRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const handleSetStartCurrent = () => {
    if (currentTime < endTime) {
      setStartTime(Math.round(currentTime * 100) / 100);
    }
  };

  const handleSetEndCurrent = () => {
    if (currentTime > startTime) {
      setEndTime(Math.round(currentTime * 100) / 100);
    }
  };

  const resetCropFull = () => {
    setCrop({
      x: 0,
      y: 0,
      width: videoWidth,
      height: videoHeight
    });
  };

  // Compute preview filename
  const baseName = evidence.original_filename.replace(/\.[^/.]+$/, "");
  let previewName = baseName;
  if (operation === 'TRIM' || operation === 'TRIM_AND_CROP') {
    const s_m = Math.floor(startTime / 60);
    const s_s = Math.floor(startTime % 60);
    const e_m = Math.floor(endTime / 60);
    const e_s = Math.floor(endTime % 60);
    previewName += `_trim_${String(s_m).padStart(2, '0')}-${String(s_s).padStart(2, '0')}_to_${String(e_m).padStart(2, '0')}-${String(e_s).padStart(2, '0')}`;
  }
  if (operation === 'CROP' || operation === 'TRIM_AND_CROP') {
    previewName += `_crop_${crop.width}x${crop.height}`;
  }
  previewName += '.mp4';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validations
    if (operation === 'TRIM' || operation === 'TRIM_AND_CROP') {
      if (startTime < 0 || endTime <= startTime || (duration > 0 && endTime > duration + 0.5)) {
        setError('Invalid trim timeline: Start must be >= 0 and End must be greater than Start.');
        return;
      }
    }

    if (operation === 'CROP' || operation === 'TRIM_AND_CROP') {
      if (crop.width <= 0 || crop.height <= 0 || crop.x < 0 || crop.y < 0 ||
          crop.x + crop.width > videoWidth || crop.y + crop.height > videoHeight) {
        setError(`Crop boundaries exceed video resolution (${videoWidth} × ${videoHeight}).`);
        return;
      }
    }

    setIsProcessing(true);

    try {
      const payload: DeriveEvidenceRequest = {
        operation,
        start_time: (operation === 'TRIM' || operation === 'TRIM_AND_CROP') ? startTime : undefined,
        end_time: (operation === 'TRIM' || operation === 'TRIM_AND_CROP') ? endTime : undefined,
        crop: (operation === 'CROP' || operation === 'TRIM_AND_CROP') ? crop : undefined
      };

      const derived = await evidenceService.deriveEvidence(caseIdentifier, evidence.id, payload);
      setIsProcessing(false);
      onClose();
      onDerivedCreated(derived);
    } catch (err: any) {
      setIsProcessing(false);
      setError(err.message || 'Failed to generate derived evidence');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm overflow-y-auto">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[95vh] flex flex-col border border-gray-200 overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-100 flex items-center justify-center text-indigo-700">
              <Film size={20} />
            </div>
            <div>
              <h2 className="text-base font-bold text-gray-900">Create Derived Evidence</h2>
              <p className="text-xs text-gray-500">
                Source: <span className="font-mono font-semibold text-gray-700">{evidence.evidence_identifier}</span> • {evidence.original_filename}
              </p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            disabled={isProcessing}
            className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Forensic Rule Callout */}
        <div className="px-6 py-2.5 bg-indigo-50/70 border-b border-indigo-100 flex items-center gap-2 text-xs text-indigo-900">
          <ShieldCheck size={16} className="text-indigo-600 shrink-0" />
          <span>
            <strong>Forensic Protection:</strong> The original evidence is strictly read-only. This operation creates an independent derived file with its own unique SHA-256 and MD5 hashes.
          </span>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
              <AlertCircle size={18} className="shrink-0 text-red-500" />
              <span>{error}</span>
            </div>
          )}

          {/* Operation Selector */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
              Derivation Operation
            </label>
            <div className="grid grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setOperation('TRIM')}
                className={`flex items-center justify-center gap-2 p-3 rounded-lg border text-sm font-semibold transition-all ${
                  operation === 'TRIM'
                    ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 shadow-sm'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                }`}
              >
                <Scissors size={18} className={operation === 'TRIM' ? 'text-indigo-600' : 'text-gray-400'} />
                Trim Video
              </button>

              <button
                type="button"
                onClick={() => setOperation('CROP')}
                className={`flex items-center justify-center gap-2 p-3 rounded-lg border text-sm font-semibold transition-all ${
                  operation === 'CROP'
                    ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 shadow-sm'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                }`}
              >
                <CropIcon size={18} className={operation === 'CROP' ? 'text-indigo-600' : 'text-gray-400'} />
                Crop Video
              </button>

              <button
                type="button"
                onClick={() => setOperation('TRIM_AND_CROP')}
                className={`flex items-center justify-center gap-2 p-3 rounded-lg border text-sm font-semibold transition-all ${
                  operation === 'TRIM_AND_CROP'
                    ? 'border-indigo-600 bg-indigo-50/50 text-indigo-900 shadow-sm'
                    : 'border-gray-200 hover:bg-gray-50 text-gray-700'
                }`}
              >
                <Film size={18} className={operation === 'TRIM_AND_CROP' ? 'text-indigo-600' : 'text-gray-400'} />
                Trim + Crop
              </button>
            </div>
          </div>

          {/* Video Preview with Crop Overlay */}
          <div className="bg-black rounded-lg overflow-hidden relative flex flex-col items-center justify-center shadow-inner">
            <div ref={containerRef} className="relative w-full max-h-[40vh] flex items-center justify-center">
              <video
                ref={videoRef}
                src={`/api/v1/cases/${caseIdentifier}/evidence/${evidence.id}/stream?access_token=${localStorage.getItem('drishtik_token')}`}
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                className="max-w-full max-h-[40vh] object-contain"
                playsInline
              />

              {/* Crop box indicator overlay */}
              {(operation === 'CROP' || operation === 'TRIM_AND_CROP') && videoWidth > 0 && (
                <div 
                  className="absolute pointer-events-none border-2 border-indigo-400 bg-indigo-500/10"
                  style={{
                    left: `${(crop.x / videoWidth) * 100}%`,
                    top: `${(crop.y / videoHeight) * 100}%`,
                    width: `${(crop.width / videoWidth) * 100}%`,
                    height: `${(crop.height / videoHeight) * 100}%`
                  }}
                >
                  <span className="absolute top-1 left-1 bg-indigo-600 text-white text-[10px] font-mono px-1 rounded shadow">
                    {crop.width} × {crop.height}
                  </span>
                </div>
              )}
            </div>

            {/* Video Controls Bar */}
            <div className="w-full bg-gray-900 px-4 py-2 flex items-center justify-between text-white text-xs border-t border-gray-800">
              <button
                type="button"
                onClick={togglePlay}
                className="p-1.5 hover:bg-gray-800 rounded text-gray-300 hover:text-white transition-colors"
              >
                {isPlaying ? <Pause size={16} /> : <Play size={16} />}
              </button>
              <div className="font-mono">
                {currentTime.toFixed(1)}s / {duration.toFixed(1)}s
              </div>
            </div>
          </div>

          {/* Trim Controls */}
          {(operation === 'TRIM' || operation === 'TRIM_AND_CROP') && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Scissors size={14} className="text-indigo-600" />
                  Timeline Selection
                </span>
                <span className="text-xs font-mono font-medium text-indigo-700">
                  Clip Duration: {Math.max(0, endTime - startTime).toFixed(2)}s
                </span>
              </div>

              {/* Range sliders */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                    <span>Start Time: {startTime.toFixed(2)}s</span>
                    <button
                      type="button"
                      onClick={handleSetStartCurrent}
                      className="text-[11px] text-indigo-600 hover:underline"
                    >
                      Set to Current ({currentTime.toFixed(1)}s)
                    </button>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={duration || 10}
                    step={0.1}
                    value={startTime}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      if (val < endTime) setStartTime(val);
                    }}
                    className="w-full accent-indigo-600 cursor-pointer"
                  />
                  <input
                    type="number"
                    min={0}
                    max={endTime - 0.1}
                    step={0.1}
                    value={startTime}
                    onChange={(e) => setStartTime(Math.max(0, parseFloat(e.target.value) || 0))}
                    className="mt-1 w-full text-xs px-2 py-1 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                    <span>End Time: {endTime.toFixed(2)}s</span>
                    <button
                      type="button"
                      onClick={handleSetEndCurrent}
                      className="text-[11px] text-indigo-600 hover:underline"
                    >
                      Set to Current ({currentTime.toFixed(1)}s)
                    </button>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={duration || 10}
                    step={0.1}
                    value={endTime}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      if (val > startTime) setEndTime(val);
                    }}
                    className="w-full accent-indigo-600 cursor-pointer"
                  />
                  <input
                    type="number"
                    min={startTime + 0.1}
                    max={duration || 10}
                    step={0.1}
                    value={endTime}
                    onChange={(e) => setEndTime(Math.min(duration || 10, parseFloat(e.target.value) || 0))}
                    className="mt-1 w-full text-xs px-2 py-1 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Crop Controls */}
          {(operation === 'CROP' || operation === 'TRIM_AND_CROP') && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                  <CropIcon size={14} className="text-indigo-600" />
                  Spatial Crop Area (Source: {videoWidth} × {videoHeight})
                </span>
                <button
                  type="button"
                  onClick={resetCropFull}
                  className="text-xs text-indigo-600 hover:text-indigo-800 flex items-center gap-1 font-medium"
                >
                  <RotateCcw size={12} /> Reset Full Frame
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">X Offset (px)</label>
                  <input
                    type="number"
                    min={0}
                    max={Math.max(0, videoWidth - crop.width)}
                    value={crop.x}
                    onChange={(e) => setCrop(c => ({ ...c, x: Math.max(0, parseInt(e.target.value) || 0) }))}
                    className="w-full text-xs px-2 py-1.5 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Y Offset (px)</label>
                  <input
                    type="number"
                    min={0}
                    max={Math.max(0, videoHeight - crop.height)}
                    value={crop.y}
                    onChange={(e) => setCrop(c => ({ ...c, y: Math.max(0, parseInt(e.target.value) || 0) }))}
                    className="w-full text-xs px-2 py-1.5 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Width (px)</label>
                  <input
                    type="number"
                    min={32}
                    max={videoWidth - crop.x}
                    value={crop.width}
                    onChange={(e) => setCrop(c => ({ ...c, width: Math.max(32, parseInt(e.target.value) || 32) }))}
                    className="w-full text-xs px-2 py-1.5 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-gray-500 mb-1">Height (px)</label>
                  <input
                    type="number"
                    min={32}
                    max={videoHeight - crop.y}
                    value={crop.height}
                    onChange={(e) => setCrop(c => ({ ...c, height: Math.max(32, parseInt(e.target.value) || 32) }))}
                    className="w-full text-xs px-2 py-1.5 bg-white border border-gray-300 rounded font-mono"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Derived File Preview Card */}
          <div className="p-3 bg-gray-100/80 rounded-lg border border-gray-200 text-xs">
            <div className="text-gray-500 font-medium mb-1">Output Evidence Preview:</div>
            <div className="font-mono text-gray-900 font-semibold break-all">{previewName}</div>
            <div className="text-gray-500 mt-1 flex items-center gap-2">
              <span>Status: <strong className="text-indigo-700">DERIVED</strong></span>
              <span>•</span>
              <span>Parent: <strong className="text-gray-700">{evidence.evidence_identifier}</strong></span>
            </div>
          </div>

        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isProcessing}
            className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 disabled:opacity-50 transition-all flex items-center gap-2 shadow-sm"
          >
            {isProcessing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Creating Derived Evidence...
              </>
            ) : (
              <>
                <Film size={16} />
                Create Derived Evidence
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}

