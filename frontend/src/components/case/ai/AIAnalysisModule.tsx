import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Brain,
  Search,
  Play,
  RotateCw,
  Eye,
  Camera,
  Layers,
  Car,
  User,
  Activity,
  Box,
  CheckCircle,
  AlertTriangle,
  ExternalLink,
  Filter,
  Info
} from 'lucide-react';
import { useAuth } from '../../../hooks/useAuth';
import { evidenceService, type Evidence } from '../../../services/evidenceService';
import {
  aiAnalysisService,
  type AIFinding,
  type AIAnalysisJob,
  type AIFrameExportResult,
} from '../../../services/aiAnalysisService';
import {
  videoAnalysisService,
  type UnifiedVideoRepresentation,
} from '../../../services/videoAnalysisService';

export function AIAnalysisModule() {
  const { caseId } = useParams();
  const { activeCase, role } = useAuth();
  const navigate = useNavigate();

  const [videos, setVideos] = useState<Evidence[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<number | null>(null);
  const [unifiedVideo, setUnifiedVideo] = useState<UnifiedVideoRepresentation | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentJob, setCurrentJob] = useState<AIAnalysisJob | null>(null);
  const [findings, setFindings] = useState<AIFinding[]>([]);
  const [isLoadingFindings, setIsLoadingFindings] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Config State
  const [detectObjects, setDetectObjects] = useState(true);
  const [detectMotion, setDetectMotion] = useState(true);
  const [sampleRate, setSampleRate] = useState(1.0);
  const [confThreshold, setConfThreshold] = useState(0.35);

  // Filters State
  const [classFilter, setClassFilter] = useState('ALL');
  const [minConfFilter, setMinConfFilter] = useState(0.30);
  const [searchQuery, setSearchQuery] = useState('');

  // Selected Finding for Details Modal
  const [selectedFinding, setSelectedFinding] = useState<AIFinding | null>(null);

  // Exported AI Frame state
  const [exportedResult, setExportedResult] = useState<AIFrameExportResult | null>(null);
  const [exportingId, setExportingId] = useState<number | null>(null);

  const canEdit = role === 'ADMIN' || role === 'INVESTIGATOR';

  // Load video evidence
  useEffect(() => {
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    evidenceService.listEvidence(caseIdent)
      .then((items: Evidence[]) => {
        const videoItems = items.filter((e) => e.media_type === 'Video' && !e.is_deleted);
        setVideos(videoItems);
        if (videoItems.length > 0 && !selectedEvidenceId) {
          setSelectedEvidenceId(videoItems[0].id);
        }
      })
      .catch((err) => {
        console.error('Failed to load video evidence:', err);
      });
  }, [caseId, activeCase]);

  // Load Unified Video Metadata when selectedEvidenceId changes (fixes Duration: Unknown bug)
  useEffect(() => {
    if (!selectedEvidenceId) {
      setUnifiedVideo(null);
      return;
    }
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    videoAnalysisService.getUnifiedVideo(caseIdent, selectedEvidenceId)
      .then((data) => setUnifiedVideo(data))
      .catch(() => setUnifiedVideo(null));
  }, [selectedEvidenceId, caseId, activeCase]);

  // Load existing findings for selected video
  useEffect(() => {
    if (!selectedEvidenceId) return;
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    setIsLoadingFindings(true);
    aiAnalysisService.listFindings(caseIdent, selectedEvidenceId)
      .then((data) => {
        setFindings(data);
      })
      .catch((err) => {
        console.error('Failed to load AI findings:', err);
      })
      .finally(() => {
        setIsLoadingFindings(false);
      });
  }, [selectedEvidenceId, caseId, activeCase]);

  // Start AI Job
  const handleStartAI = async () => {
    if (!selectedEvidenceId || !activeCase) return;
    setIsAnalyzing(true);
    setError(null);
    try {
      const job = await aiAnalysisService.startJob(activeCase.case_identifier, selectedEvidenceId, {
        sample_rate_fps: sampleRate,
        confidence_threshold: confThreshold,
        detect_objects: detectObjects,
        detect_motion: detectMotion,
      });
      setCurrentJob(job);
      setFindings(job.findings);
    } catch (err: any) {
      setError(err.detail || 'AI analysis execution failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Export AI Frame
  const handleExportFrame = async (findingId: number) => {
    if (!selectedEvidenceId || !activeCase) return;
    setExportingId(findingId);
    try {
      const res = await aiAnalysisService.exportFrame(activeCase.case_identifier, selectedEvidenceId, findingId);
      setExportedResult(res);
    } catch (err: any) {
      alert(err.detail || 'Failed to export AI finding frame');
    } finally {
      setExportingId(null);
    }
  };

  // Filtered findings
  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (classFilter !== 'ALL') {
        if (classFilter === 'Person' && f.object_class.toLowerCase() !== 'person') return false;
        if (classFilter === 'Vehicle' && !['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'vehicle'].includes(f.object_class.toLowerCase())) return false;
        if (classFilter === 'Motion' && f.object_class.toLowerCase() !== 'motion') return false;
        if (classFilter === 'Object' && ['person', 'motion', 'car', 'truck', 'bus', 'motorcycle', 'bicycle'].includes(f.object_class.toLowerCase())) return false;
      }
      if (f.confidence < minConfFilter) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          f.object_class.toLowerCase().includes(q) ||
          f.finding_identifier.toLowerCase().includes(q) ||
          f.model_name.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [findings, classFilter, minConfFilter, searchQuery]);

  const selectedVideo = videos.find((v) => v.id === selectedEvidenceId);

  const formatMediaTime = (seconds: number) => {
    const s = Math.floor(seconds % 60);
    const m = Math.floor((seconds / 60) % 60);
    const h = Math.floor(seconds / 3600);
    if (h > 0) {
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  // Format Duration display (e.g. 00:12)
  const formatDurationDisplay = (dur?: number | null) => {
    if (dur === undefined || dur === null || isNaN(dur) || dur <= 0) return 'Unknown';
    const totalSec = Math.floor(dur);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    const h = Math.floor(totalSec / 3600);
    if (h > 0) {
      return `${String(h).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const durationDisplay = formatDurationDisplay(unifiedVideo?.duration_seconds ?? selectedVideo?.duration_seconds);
  const resolutionDisplay = (unifiedVideo?.width && unifiedVideo?.height) 
    ? `${unifiedVideo.width}×${unifiedVideo.height}` 
    : (selectedVideo?.width && selectedVideo?.height) 
    ? `${selectedVideo.width}×${selectedVideo.height}` 
    : 'Unknown';
  const fpsDisplay = unifiedVideo?.fps ? `${unifiedVideo.fps}` : selectedVideo?.fps ? `${selectedVideo.fps}` : 'Unknown';
  const codecDisplay = unifiedVideo?.video_codec || selectedVideo?.video_codec || 'Unknown';
  const channelsDisplay = unifiedVideo?.channel_name || (selectedVideo?.channel_index ? `CAM ${String(selectedVideo.channel_index).padStart(2, '0')}` : 'CAM 01');

  return (
    <div className="h-full flex flex-col bg-slate-50 text-gray-900 p-6 overflow-y-auto font-sans">
      
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-lg">
            <Brain size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">AI Video Intelligence & Detection</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Automated object detection and motion analysis with forensic timestamp tracking.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 bg-white border border-gray-200 rounded text-xs text-gray-600 font-mono shadow-xs">
            Model: <strong className="text-indigo-700">YOLOv8n + OpenCV-MOG2</strong>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md flex items-center gap-2">
          <AlertTriangle size={16} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Video Selection & AI Configuration Bar */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6 shadow-xs space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 items-end">
          
          {/* Select Video */}
          <div className="lg:col-span-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
              Select CCTV Video Evidence for AI Analysis
            </label>
            <select
              value={selectedEvidenceId || ''}
              onChange={(e) => setSelectedEvidenceId(Number(e.target.value))}
              className="w-full bg-white border border-gray-300 text-gray-800 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer shadow-xs font-medium"
            >
              {videos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.evidence_identifier} — {v.original_filename} ({v.duration_seconds ? `${v.duration_seconds.toFixed(1)}s` : 'Video Stream'})
                </option>
              ))}
            </select>
          </div>

          {/* Sampling Rate */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
              Frame Sampling Rate
            </label>
            <select
              value={sampleRate}
              onChange={(e) => setSampleRate(parseFloat(e.target.value))}
              className="w-full bg-white border border-gray-300 text-gray-800 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer shadow-xs font-medium"
            >
              <option value={0.5}>0.5 FPS (Every 2 seconds)</option>
              <option value={1.0}>1.0 FPS (Default: Every 1 second)</option>
              <option value={2.0}>2.0 FPS (Every 0.5 second)</option>
              <option value={5.0}>5.0 FPS (Dense sampling)</option>
            </select>
          </div>

          {/* Start Action */}
          <div>
            <button
              onClick={handleStartAI}
              disabled={isAnalyzing || !selectedEvidenceId || !canEdit}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-md text-xs font-semibold flex items-center justify-center gap-2 transition-colors shadow-xs"
            >
              {isAnalyzing ? (
                <>
                  <RotateCw size={15} className="animate-spin" />
                  Analyzing Video...
                </>
              ) : (
                <>
                  <Play size={15} />
                  Start AI Analysis
                </>
              )}
            </button>
          </div>
        </div>

        {/* Options & Confidence Threshold Slider */}
        <div className="pt-4 border-t border-gray-100 flex flex-wrap items-center justify-between gap-4 text-xs text-gray-700">
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer select-none font-medium">
              <input
                type="checkbox"
                checked={detectObjects}
                onChange={(e) => setDetectObjects(e.target.checked)}
                className="rounded accent-indigo-600 cursor-pointer"
              />
              <span>YOLO Object Detection (Person, Vehicle, Objects)</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer select-none font-medium">
              <input
                type="checkbox"
                checked={detectMotion}
                onChange={(e) => setDetectMotion(e.target.checked)}
                className="rounded accent-indigo-600 cursor-pointer"
              />
              <span>OpenCV Motion Detection</span>
            </label>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-gray-500 font-medium">Confidence Threshold:</span>
            <input
              type="range"
              min={0.15}
              max={0.90}
              step={0.05}
              value={confThreshold}
              onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
              className="w-24 h-1.5 bg-gray-200 rounded appearance-none cursor-pointer accent-indigo-600"
            />
            <span className="font-mono text-indigo-700 font-bold">{Math.round(confThreshold * 100)}%</span>
          </div>
        </div>

        {/* Unified Forensic Video Metadata Bar (Fixed Display) */}
        {selectedVideo && (
          <div className="pt-3 border-t border-gray-100 flex flex-wrap items-center justify-between text-xs text-gray-500 font-mono">
            <div className="flex flex-wrap items-center gap-6">
              <div>Duration: <strong className="text-gray-900 font-bold">{durationDisplay}</strong></div>
              <div>Resolution: <strong className="text-gray-900 font-bold">{resolutionDisplay}</strong></div>
              <div>FPS: <strong className="text-gray-900 font-bold">{fpsDisplay}</strong></div>
              <div>Codec: <strong className="text-gray-900 font-bold">{codecDisplay}</strong></div>
              <div>Channels: <strong className="text-indigo-700 font-bold">{channelsDisplay}</strong></div>
            </div>
            {currentJob && (
              <div className="text-indigo-700 font-sans font-semibold">
                Job: {currentJob.job_identifier} ({currentJob.total_frames_analyzed} frames analyzed)
              </div>
            )}
          </div>
        )}
      </div>

      {isLoadingFindings && (
        <div className="text-xs text-gray-500 mb-2 flex items-center gap-2">
          <RotateCw size={12} className="animate-spin text-indigo-600" /> Loading AI findings...
        </div>
      )}

      {/* Filter and Findings Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        
        {/* Class Filter Tabs */}
        <div className="flex items-center gap-1 bg-gray-100 p-1 rounded-lg border border-gray-200 text-xs font-semibold">
          {[
            { id: 'ALL', label: 'All Classes', icon: Layers },
            { id: 'Person', label: 'Persons', icon: User },
            { id: 'Vehicle', label: 'Vehicles', icon: Car },
            { id: 'Motion', label: 'Motion', icon: Activity },
            { id: 'Object', label: 'Objects', icon: Box },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setClassFilter(tab.id)}
                className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors ${
                  classFilter === tab.id 
                    ? 'bg-white text-indigo-700 font-bold shadow-xs' 
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Search & Confidence Filter */}
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search findings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-white border border-gray-300 text-gray-800 rounded-md pl-8 pr-3 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 w-48 shadow-xs"
            />
          </div>

          <div className="flex items-center gap-2 bg-white border border-gray-200 px-3 py-1.5 rounded-md text-xs text-gray-700 shadow-xs">
            <Filter size={13} className="text-gray-400" />
            <span className="text-gray-500 font-medium">Min Conf:</span>
            <input
              type="range"
              min={0.15}
              max={0.90}
              step={0.05}
              value={minConfFilter}
              onChange={(e) => setMinConfFilter(parseFloat(e.target.value))}
              className="w-16 h-1 bg-gray-200 rounded appearance-none cursor-pointer accent-indigo-600"
            />
            <span className="font-mono text-indigo-700 font-bold">{Math.round(minConfFilter * 100)}%</span>
          </div>
        </div>
      </div>

      {/* Findings Grid / Cards */}
      <div className="flex-1 bg-white border border-gray-200 rounded-lg p-4 shadow-xs overflow-y-auto">
        {filteredFindings.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-500 space-y-3">
            <Brain size={40} className="opacity-30 text-gray-400" />
            <p className="text-sm font-bold text-gray-700">No AI findings yet</p>
            <p className="text-xs max-w-md text-center text-gray-500">
              Run AI Analysis to generate object and motion findings for this evidence.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {filteredFindings.map((finding) => (
              <div
                key={finding.id}
                className="bg-white border border-gray-200 hover:border-gray-300 rounded-lg p-3.5 flex flex-col justify-between space-y-3 transition-colors shadow-xs"
              >
                <div>
                  {/* Card Header: Class & Confidence */}
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider flex items-center gap-1 ${
                        finding.object_class.toLowerCase() === 'person'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : ['car', 'truck', 'bus', 'motorcycle', 'vehicle'].includes(finding.object_class.toLowerCase())
                          ? 'bg-amber-50 text-amber-800 border border-amber-200'
                          : finding.object_class.toLowerCase() === 'motion'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-purple-50 text-purple-700 border border-purple-200'
                      }`}
                    >
                      {finding.object_class}
                    </span>
                    <span className="text-[11px] font-mono text-gray-500">
                      Model confidence: <strong className="text-gray-900 font-bold">{Math.round(finding.confidence * 100)}%</strong>
                    </span>
                  </div>

                  {/* Finding Identifier */}
                  <div className="font-mono text-[10px] text-gray-400 mb-1.5">
                    {finding.finding_identifier}
                  </div>

                  {/* Timestamp & Provenance info */}
                  <div className="space-y-1 font-mono text-xs text-gray-700">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Media Time:</span>
                      <span className="text-indigo-700 font-bold">{formatMediaTime(finding.media_time)}</span>
                    </div>
                    {finding.source_timestamp ? (
                      <div className="flex justify-between">
                        <span className="text-gray-500">CCTV Time:</span>
                        <span className="text-emerald-700 font-medium truncate max-w-[140px]">
                          {new Date(finding.source_timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ) : (
                      <div className="flex justify-between">
                        <span className="text-gray-500">CCTV Time:</span>
                        <span className="text-gray-400 italic">Unavailable</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-500">Channel:</span>
                      <span className="text-gray-800 font-medium">{channelsDisplay}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Frame:</span>
                      <span className="text-gray-800 font-medium">#{Math.round(finding.media_time * (unifiedVideo?.fps || 25))}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Status:</span>
                      <span className="text-emerald-700 font-semibold uppercase text-[10px]">VERIFIED</span>
                    </div>
                  </div>
                </div>

                {/* Actions: Review Frame, Details, Export Frame */}
                <div className="pt-2 border-t border-gray-100 flex items-center justify-between gap-1.5 font-sans">
                  <button
                    onClick={() => {
                      navigate(`/case/${caseId}/video?t=${finding.media_time}`);
                    }}
                    className="px-2 py-1 bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 rounded text-[11px] font-medium flex items-center gap-1 transition-colors shadow-xs"
                    title="Open exact frame in Video Analysis Workspace"
                  >
                    <Eye size={12} />
                    Review Frame
                  </button>

                  <button
                    onClick={() => setSelectedFinding(finding)}
                    className="px-2 py-1 bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 rounded text-[11px] font-medium flex items-center gap-1 transition-colors shadow-xs"
                    title="Inspect finding details"
                  >
                    <Info size={12} />
                    Details
                  </button>

                  {canEdit && (
                    <button
                      onClick={() => handleExportFrame(finding.id)}
                      disabled={exportingId === finding.id}
                      className="px-2 py-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded text-[11px] font-semibold flex items-center gap-1 transition-colors shadow-xs"
                      title="Export this AI finding frame as a new DERIVED evidence artifact"
                    >
                      <Camera size={12} />
                      {exportingId === finding.id ? 'Exporting...' : 'Export Frame'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Details Modal */}
      {selectedFinding && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-lg max-w-md w-full p-5 space-y-4 shadow-xl text-xs text-gray-800">
            <div className="flex items-center justify-between text-gray-900 font-bold text-sm">
              <span className="flex items-center gap-2">
                <Brain size={18} className="text-indigo-600" /> Finding Details: {selectedFinding.finding_identifier}
              </span>
              <button onClick={() => setSelectedFinding(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded p-3 space-y-2 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-gray-500">Class:</span>
                <span className="text-indigo-700 font-bold uppercase">{selectedFinding.object_class}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Confidence:</span>
                <span className="text-gray-900 font-bold">{(selectedFinding.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Media Time:</span>
                <span className="text-gray-900">{formatMediaTime(selectedFinding.media_time)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Channel:</span>
                <span className="text-gray-900">{channelsDisplay}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Frame Number:</span>
                <span className="text-gray-900">#{Math.round(selectedFinding.media_time * (unifiedVideo?.fps || 25))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Model Engine:</span>
                <span className="text-gray-900">{selectedFinding.model_name}</span>
              </div>
              {selectedFinding.bounding_box && (
                <div className="border-t border-gray-200 pt-1 mt-1">
                  <div className="text-gray-500 mb-0.5">Bounding Coordinates:</div>
                  <div className="text-[10px] text-gray-700 font-mono break-all">{selectedFinding.bounding_box}</div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedFinding(null)}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded font-medium border border-gray-200"
              >
                Close
              </button>
              <button
                onClick={() => {
                  const targetTime = selectedFinding.media_time;
                  setSelectedFinding(null);
                  navigate(`/case/${caseId}/video?t=${targetTime}`);
                }}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold flex items-center gap-1.5 shadow-xs"
              >
                <Eye size={13} /> Open in Video Analysis
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Exported AI Frame Modal */}
      {exportedResult && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-emerald-500 rounded-lg max-w-md w-full p-5 space-y-4 shadow-xl text-xs text-gray-800">
            <div className="flex items-center justify-between text-emerald-700 font-bold text-sm">
              <span className="flex items-center gap-2">
                <CheckCircle size={18} /> AI Frame Exported as Derived Artifact
              </span>
              <button onClick={() => setExportedResult(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <p className="text-gray-600">
              A new <strong>DERIVED</strong> evidence artifact has been generated for this AI detection. The original video remains strictly unmodified.
            </p>

            <div className="bg-gray-50 border border-gray-200 rounded p-3 space-y-2 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-gray-500">Derived Evidence ID:</span>
                <span className="text-indigo-700 font-bold">{exportedResult.evidence_identifier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Operation:</span>
                <span className="text-purple-700 font-bold">{exportedResult.derived_operation}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Media Time:</span>
                <span className="text-gray-900">{formatMediaTime(exportedResult.media_time)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">File Size:</span>
                <span className="text-gray-800">{(exportedResult.size_bytes / 1024).toFixed(1)} KB</span>
              </div>
              <div className="border-t border-gray-200 pt-1">
                <div className="text-gray-500 mb-0.5">SHA-256 Hash:</div>
                <div className="text-[10px] text-emerald-700 break-all select-all font-mono">{exportedResult.sha256}</div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setExportedResult(null)}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded font-medium border border-gray-200"
              >
                Close
              </button>
              <button
                onClick={() => {
                  setExportedResult(null);
                  navigate(`/case/${caseId}/evidence/${exportedResult.evidence_id}`);
                }}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold flex items-center gap-1.5 shadow-xs"
              >
                <ExternalLink size={13} /> View Derived Artifact
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
