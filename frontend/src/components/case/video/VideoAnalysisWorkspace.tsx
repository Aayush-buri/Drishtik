import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  Pause,
  ChevronLeft,
  ChevronRight,
  Volume2,
  VolumeX,
  Maximize2,
  Camera,
  FileText,
  Bookmark,
  Sliders,
  Info,
  Search,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Copy,
  ExternalLink,
  Grid
} from 'lucide-react';
import { useAuth } from '../../../hooks/useAuth';
import { evidenceService } from '../../../services/evidenceService';
import type { Evidence } from '../../../services/evidenceService';
import {
  videoAnalysisService,
  type UnifiedVideoRepresentation,
  type TimelineEvent,
  type AnalysisNote,
  type TimestampCalibration,
  type FrameExportResponse,
} from '../../../services/videoAnalysisService';
import { ForensicFormatAdvisory } from '../evidence/ForensicFormatAdvisory';
import { HexPreviewModal } from '../evidence/HexPreviewModal';

export function VideoAnalysisWorkspace() {
  const { caseId, evidenceId } = useParams();
  const { activeCase, role } = useAuth();
  const navigate = useNavigate();

  // State: Evidence & Representation
  const [unifiedVideo, setUnifiedVideo] = useState<UnifiedVideoRepresentation | null>(null);
  const [availableVideos, setAvailableVideos] = useState<Evidence[]>([]);
  const [activeEvidenceId, setActiveEvidenceId] = useState<number | null>(
    evidenceId ? parseInt(evidenceId) : null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(1.0);
  const [isHexPreviewOpen, setIsHexPreviewOpen] = useState(false);

  // Timeline state
  const timelineRef = useRef<HTMLDivElement>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1); // 1x, 2x, 5x, 10x
  const [isMultiView, setIsMultiView] = useState(false);

  // Tabs state
  const [activeTab, setActiveTab] = useState<'events' | 'notes' | 'calibration' | 'metadata'>('events');

  // Events & Notes state
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [notes, setNotes] = useState<AnalysisNote[]>([]);
  const [eventSearch, setEventSearch] = useState('');
  const [noteSearch, setNoteSearch] = useState('');
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  // New Event Form
  const [isAddingEvent, setIsAddingEvent] = useState(false);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventType, setNewEventType] = useState('Observation');
  const [newEventDesc, setNewEventDesc] = useState('');

  // New Note Form
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [newNoteText, setNewNoteText] = useState('');

  // Calibration Form
  const [calibration, setCalibration] = useState<TimestampCalibration | null>(null);
  const [calibOffset, setCalibOffset] = useState<number>(0);
  const [calibTimezone, setCalibTimezone] = useState('UTC');
  const [calibReason, setCalibReason] = useState('');
  const [calibSuccessMsg, setCalibSuccessMsg] = useState<string | null>(null);

  // Frame Export notification
  const [exportedFrame, setExportedFrame] = useState<FrameExportResponse | null>(null);
  const [isExportingFrame, setIsExportingFrame] = useState(false);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const canEdit = role === 'ADMIN' || role === 'INVESTIGATOR';

  // 1. Initial Load: If no evidenceId, fetch video evidence list in case to auto-select
  useEffect(() => {
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    evidenceService.listEvidence(caseIdent)
      .then((items: Evidence[]) => {
        const videoItems = items.filter((ev: Evidence) => ev.media_type === 'Video' && !ev.is_deleted);
        setAvailableVideos(videoItems);
        if (!activeEvidenceId && videoItems.length > 0) {
          setActiveEvidenceId(videoItems[0].id);
        }
      })
      .catch((err: any) => {
        console.error('Failed to load case evidence items:', err);
      });
  }, [caseId, activeCase]);

  // 2. Load Unified Video Representation when activeEvidenceId changes
  useEffect(() => {
    if (!activeEvidenceId) return;
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    setIsLoading(true);
    setError(null);

    Promise.all([
      videoAnalysisService.getUnifiedVideo(caseIdent, activeEvidenceId),
      videoAnalysisService.getTimelineEvents(caseIdent, activeEvidenceId),
      videoAnalysisService.getAnalysisNotes(caseIdent, activeEvidenceId),
      videoAnalysisService.getCalibration(caseIdent, activeEvidenceId),
    ])
      .then(([unified, evtList, noteList, calib]) => {
        setUnifiedVideo(unified);
        setDuration(unified.duration_seconds || 0);
        setEvents(evtList);
        setNotes(noteList);
        setCalibration(calib);
        if (calib) {
          setCalibOffset(calib.offset_seconds);
          setCalibTimezone(calib.time_zone);
          setCalibReason(calib.calibration_reason || '');
        } else {
          setCalibOffset(unified.offset_seconds || 0);
          setCalibTimezone(unified.timezone || 'UTC');
          setCalibReason(unified.calibration_reason || '');
        }
      })
      .catch((err) => {
        setError(err.detail || 'Failed to initialize unified video analysis layer.');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [activeEvidenceId, caseId, activeCase]);

  // Video element event listeners
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onTimeUpdate = () => {
      setCurrentTime(video.currentTime);
    };
    const onLoadedMetadata = () => {
      setDuration(video.duration || unifiedVideo?.duration_seconds || 0);
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('loadedmetadata', onLoadedMetadata);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);

    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('loadedmetadata', onLoadedMetadata);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
    };
  }, [unifiedVideo]);

  // Playback rate handler
  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
  };

  // Play / Pause toggle
  const togglePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(console.error);
    } else {
      video.pause();
    }
  };

  // Frame Stepping
  const stepFrame = (delta: number) => {
    const video = videoRef.current;
    if (!video) return;
    if (!video.paused) {
      video.pause();
    }
    const fps = unifiedVideo?.fps || 25.0;
    const stepDuration = 1.0 / fps;
    const nextTime = Math.max(0, Math.min(video.duration || duration, video.currentTime + delta * stepDuration));
    video.currentTime = nextTime;
    setCurrentTime(nextTime);
  };

  // Volume & Mute
  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleVolumeChange = (val: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.volume = val;
    setVolume(val);
    if (val === 0) {
      setIsMuted(true);
      video.muted = true;
    } else if (isMuted) {
      setIsMuted(false);
      video.muted = false;
    }
  };

  // Fullscreen
  const toggleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(console.error);
    } else {
      video.requestFullscreen().catch(console.error);
    }
  };

  // Frame Export
  const handleExportFrame = async () => {
    if (!activeEvidenceId || !activeCase) return;
    setIsExportingFrame(true);
    try {
      const res = await videoAnalysisService.exportFrame(activeCase.case_identifier, activeEvidenceId, {
        media_time: currentTime,
        frame_number: Math.round(currentTime * (unifiedVideo?.fps || 25.0)),
      });
      setExportedFrame(res);
    } catch (err: any) {
      alert(err.detail || 'Failed to export frame');
    } finally {
      setIsExportingFrame(false);
    }
  };

  // Timeline Seek
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;
    const effectiveDuration = duration || unifiedVideo?.duration_seconds || 1;
    const newTime = Math.max(0, Math.min(effectiveDuration, (clickX / width) * effectiveDuration));
    if (videoRef.current) {
      videoRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
  };

  // Timeline Event Navigation (Prev / Next)
  const sortedEvents = useMemo(() => {
    return [...events].sort((a, b) => a.media_time - b.media_time);
  }, [events]);

  const goToPrevEvent = () => {
    if (sortedEvents.length === 0) return;
    const prev = [...sortedEvents].reverse().find((e) => e.media_time < currentTime - 0.1);
    const target = prev || sortedEvents[0];
    seekToTime(target.media_time);
    setSelectedEventId(target.id);
  };

  const goToNextEvent = () => {
    if (sortedEvents.length === 0) return;
    const next = sortedEvents.find((e) => e.media_time > currentTime + 0.1);
    const target = next || sortedEvents[sortedEvents.length - 1];
    seekToTime(target.media_time);
    setSelectedEventId(target.id);
  };

  const seekToTime = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = t;
    }
    setCurrentTime(t);
  };

  // Format Helpers
  const formatMediaTime = (seconds: number) => {
    const totalMs = Math.floor(seconds * 1000);
    const ms = totalMs % 1000;
    const totalSec = Math.floor(totalMs / 1000);
    const s = totalSec % 60;
    const m = Math.floor(totalSec / 60) % 60;
    const h = Math.floor(totalSec / 3600);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  };

  const formatShortTime = (seconds: number) => {
    const totalSec = Math.floor(seconds);
    const s = totalSec % 60;
    const m = Math.floor(totalSec / 60) % 60;
    const h = Math.floor(totalSec / 3600);
    if (h > 0) {
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  // Compute Current CCTV Timestamp (Source vs Calibrated)
  const { currentSourceTimestamp, currentCalibratedTimestamp } = useMemo(() => {
    if (!unifiedVideo?.source_start_time) {
      return { currentSourceTimestamp: 'Unavailable', currentCalibratedTimestamp: 'Not applied' };
    }
    try {
      const baseDate = new Date(unifiedVideo.source_start_time);
      const srcMs = baseDate.getTime() + currentTime * 1000;
      const srcDate = new Date(srcMs);
      const srcStr = srcDate.toISOString().replace('T', ' ').replace('Z', '');

      const offset = calibration ? calibration.offset_seconds : (unifiedVideo.offset_seconds || 0);
      if (offset !== 0 || unifiedVideo.is_calibrated) {
        const calibDate = new Date(srcMs + offset * 1000);
        const calibStr = calibDate.toISOString().replace('T', ' ').replace('Z', '');
        return { currentSourceTimestamp: srcStr, currentCalibratedTimestamp: calibStr };
      }
      return { currentSourceTimestamp: srcStr, currentCalibratedTimestamp: 'Not applied' };
    } catch {
      return { currentSourceTimestamp: 'Unavailable', currentCalibratedTimestamp: 'Not applied' };
    }
  }, [unifiedVideo, currentTime, calibration]);

  // Add Timeline Event
  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEventTitle.trim() || !activeEvidenceId || !activeCase) return;

    try {
      const created = await videoAnalysisService.createTimelineEvent(activeCase.case_identifier, activeEvidenceId, {
        media_time: currentTime,
        title: newEventTitle.trim(),
        event_type: newEventType,
        description: newEventDesc.trim() || undefined,
        channel_id: unifiedVideo?.channel_number || 1,
      });
      setEvents((prev) => [...prev, created]);
      setNewEventTitle('');
      setNewEventDesc('');
      setIsAddingEvent(false);
    } catch (err: any) {
      alert(err.detail || 'Failed to save timeline event');
    }
  };

  // Delete Timeline Event
  const handleDeleteEvent = async (id: number) => {
    if (!activeCase || !window.confirm('Delete this timeline event marker?')) return;
    try {
      await videoAnalysisService.deleteTimelineEvent(activeCase.case_identifier, id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      if (selectedEventId === id) setSelectedEventId(null);
    } catch (err: any) {
      alert(err.detail || 'Failed to delete event');
    }
  };

  // Add Investigator Note
  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteText.trim() || !activeEvidenceId || !activeCase) return;

    try {
      const created = await videoAnalysisService.createAnalysisNote(activeCase.case_identifier, activeEvidenceId, {
        media_time: currentTime,
        note_text: newNoteText.trim(),
      });
      setNotes((prev) => [...prev, created]);
      setNewNoteText('');
      setIsAddingNote(false);
    } catch (err: any) {
      alert(err.detail || 'Failed to save analysis note');
    }
  };

  // Delete Investigator Note
  const handleDeleteNote = async (id: number) => {
    if (!activeCase || !window.confirm('Delete this investigator note?')) return;
    try {
      await videoAnalysisService.deleteAnalysisNote(activeCase.case_identifier, id);
      setNotes((prev) => prev.filter((n) => n.id !== id));
    } catch (err: any) {
      alert(err.detail || 'Failed to delete note');
    }
  };

  // Save Timestamp Calibration
  const handleSaveCalibration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeEvidenceId || !activeCase) return;

    try {
      const res = await videoAnalysisService.setCalibration(activeCase.case_identifier, activeEvidenceId, {
        offset_seconds: Number(calibOffset),
        time_zone: calibTimezone,
        calibration_reason: calibReason.trim() || undefined,
        calibration_method: 'MANUAL_EXTERNAL_REFERENCE',
      });
      setCalibration(res);
      setCalibSuccessMsg('Calibration saved successfully. Embedded raw timestamp remains unchanged.');
      setTimeout(() => setCalibSuccessMsg(null), 4000);
    } catch (err: any) {
      alert(err.detail || 'Failed to save calibration');
    }
  };

  // Copy hash helper
  const copyHash = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Loading Screen
  if (isLoading && !unifiedVideo) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-gray-950 text-gray-400 space-y-4">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500"></div>
        <p className="text-sm font-medium tracking-wide">Initializing Unified Forensic Analysis Workspace...</p>
      </div>
    );
  }

  // Error Screen
  if (error || !unifiedVideo) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-gray-950 text-gray-400 p-6">
        <AlertTriangle size={48} className="text-amber-500 mb-4" />
        <h2 className="text-lg font-bold text-white mb-2">Video Analysis Error</h2>
        <p className="text-sm text-gray-400 max-w-md text-center mb-6">{error || 'No video evidence selected or available.'}</p>
        <button
          onClick={() => navigate(`/case/${caseId}/evidence`)}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm font-medium flex items-center gap-2"
        >
          <ArrowLeft size={16} /> Back to Evidence
        </button>
      </div>
    );
  }

  const currentFrameNumber = Math.round(currentTime * (unifiedVideo.fps || 25.0));

  // Determine effective streaming source URL
  const token = localStorage.getItem('drishtik_token') || '';
  const streamUrl = unifiedVideo.playback_source 
    ? `${unifiedVideo.playback_source}?access_token=${token}` 
    : `/api/v1/cases/${activeCase?.case_identifier}/evidence/${unifiedVideo.evidence_id}/stream?access_token=${token}`;

  return (
    <div className="h-full flex flex-col bg-gray-950 text-gray-100 select-none overflow-hidden">
      
      {/* TOP BAR: Navigation, Evidence provenance, Status */}
      <header className="bg-gray-900 border-b border-gray-800 px-4 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(`/case/${caseId}/evidence/${unifiedVideo.evidence_id}`)}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors flex items-center gap-1.5 text-xs font-medium"
            title="Back to Evidence Inspection"
          >
            <ArrowLeft size={16} /> Back to Evidence
          </button>
          <div className="h-4 w-px bg-gray-700" />
          
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-800/80">
              {unifiedVideo.evidence_identifier}
            </span>
            <span className="text-sm font-semibold text-white tracking-wide truncate max-w-[280px]">
              {unifiedVideo.original_filename}
            </span>
            {unifiedVideo.is_inspection_proxy ? (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-900/60 text-purple-300 border border-purple-700/60">
                Derived Proxy
              </span>
            ) : (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                Original
              </span>
            )}
          </div>
        </div>

        {/* Camera Selector / Provenance Info */}
        <div className="flex items-center gap-4 text-xs">
          {availableVideos.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400 font-medium">Channel:</span>
              <select
                value={activeEvidenceId || ''}
                onChange={(e) => setActiveEvidenceId(Number(e.target.value))}
                className="bg-gray-800 border border-gray-700 text-white rounded px-2.5 py-1 text-xs focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                {availableVideos.map((v) => (
                  <option key={v.id} value={v.id}>
                    CAM {v.channel_index || 1}: {v.original_filename}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="hidden md:flex items-center gap-3 text-gray-400">
            <span>Device: <strong className="text-gray-200">{unifiedVideo.source_device_identifier || 'Not available'}</strong></span>
            <span>Acq: <strong className="text-gray-200">{unifiedVideo.acquisition_identifier || 'Not available'}</strong></span>
            <span>Vendor: <strong className="text-indigo-300">{unifiedVideo.vendor}</strong></span>
          </div>

          <button
            onClick={() => setIsMultiView(!isMultiView)}
            className={`px-2.5 py-1 rounded text-xs font-medium flex items-center gap-1.5 transition-colors ${
              isMultiView ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            <Grid size={14} />
            {isMultiView ? 'Single View' : 'Multi-View Grid'}
          </button>
        </div>
      </header>

      {/* INSPECTION PROXY BANNER (if derived proxy) */}
      {unifiedVideo.is_inspection_proxy && (
        <div className="bg-indigo-950/90 border-b border-indigo-800 px-4 py-1.5 flex items-center justify-between text-xs text-indigo-200 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
            <span className="font-bold tracking-wider text-white">PLAYING: DERIVED INSPECTION PROXY</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Original Evidence:</span>
            <span className="font-mono font-bold text-amber-300">{unifiedVideo.parent_evidence_identifier || 'EVD-ORIGINAL'}</span>
          </div>
        </div>
      )}

      {/* MAIN WORKSPACE BODY: Video Player Area */}
      <div className="flex-1 flex flex-col min-h-0 bg-black relative">
        
        {/* VIDEO DISPLAY CONTAINER */}
        <div className="flex-1 flex items-center justify-center p-3 relative overflow-hidden">
          {unifiedVideo.browser_playable ? (
            isMultiView && unifiedVideo.camera_tracks.filter(t => t.browser_playable).length > 1 ? (
              /* MULTI-VIEW GRID */
              <div className="w-full h-full grid grid-cols-2 gap-2 p-2">
                {unifiedVideo.camera_tracks.filter(t => t.browser_playable).map((track) => (
                  <div key={track.evidence_id} className={`relative bg-gray-900 rounded border ${track.is_active ? 'border-indigo-500' : 'border-gray-800'} flex flex-col overflow-hidden`}>
                    <div className="absolute top-2 left-2 z-10 bg-black/80 px-2 py-0.5 rounded text-[11px] font-mono text-white flex items-center gap-2">
                      <span className="font-bold text-indigo-400">{track.channel_name}</span>
                      <span className="text-gray-400">{track.evidence_identifier}</span>
                    </div>
                    {track.is_active ? (
                      <video
                        ref={videoRef}
                        src={streamUrl}
                        preload="metadata"
                        className="w-full h-full object-contain cursor-pointer"
                        onClick={togglePlayPause}
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center text-gray-500 text-xs">
                        <Camera size={32} className="opacity-40 mb-2" />
                        <span>{track.channel_name} ({track.vendor})</span>
                        <button
                          onClick={() => setActiveEvidenceId(track.evidence_id)}
                          className="mt-2 text-indigo-400 hover:text-indigo-300 underline text-xs"
                        >
                          Switch Active
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              /* SINGLE FORENSIC PLAYER */
              <video
                ref={videoRef}
                src={streamUrl}
                preload="metadata"
                className="max-w-full max-h-full aspect-video object-contain outline-none shadow-2xl cursor-pointer"
                onClick={togglePlayPause}
              >
                Forensic preview stream unavailable
              </video>
            )
          ) : (
            /* UNSUPPORTED PROPRIETARY FORMAT ADVISORY */
            <div className="w-full max-w-2xl bg-gray-900 border border-gray-800 rounded-lg p-6 shadow-2xl">
              <ForensicFormatAdvisory
                evidence={{
                  id: unifiedVideo.evidence_id,
                  case_id: Number(activeCase?.id || 0),
                  evidence_identifier: unifiedVideo.evidence_identifier,
                  original_filename: unifiedVideo.original_filename,
                  source_type: 'FILE_UPLOAD',
                  media_type: 'Video',
                  file_extension: '',
                  size_bytes: 0,
                  integrity_status: 'VERIFIED',
                  processing_status: 'COMPLETED',
                  evidence_status: unifiedVideo.is_inspection_proxy ? 'DERIVED' : 'ORIGINAL',
                  created_at: '',
                  imported_by: 0,
                  vendor: unifiedVideo.vendor,
                  proprietary_format: unifiedVideo.container_format,
                  is_natively_playable: false,
                }}
                caseId={activeCase?.case_identifier || caseId || ''}
                onOpenHexPreview={() => setIsHexPreviewOpen(true)}
                onProxyGenerated={(proxy) => {
                  setActiveEvidenceId(proxy.id);
                }}
              />
            </div>
          )}

          {/* DUAL TIMESTAMP & FRAME OSD OVERLAY */}
          <div className="absolute top-4 right-4 bg-black/80 backdrop-blur-sm border border-gray-800 rounded-md p-2.5 text-xs font-mono space-y-1 z-20 pointer-events-none shadow-xl">
            <div className="flex items-center justify-between gap-4">
              <span className="text-gray-400">FRAME:</span>
              <span className="text-indigo-300 font-bold">{currentFrameNumber}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-gray-400">MEDIA:</span>
              <span className="text-white font-semibold">{formatMediaTime(currentTime)}</span>
            </div>
            <div className="flex items-center justify-between gap-4 border-t border-gray-800/80 pt-1">
              <span className="text-gray-400">CCTV:</span>
              <span className="text-emerald-400 font-semibold">{currentSourceTimestamp}</span>
            </div>
            {currentCalibratedTimestamp !== 'Not applied' && (
              <div className="flex items-center justify-between gap-4">
                <span className="text-gray-400">CALIB:</span>
                <span className="text-amber-400 font-semibold">{currentCalibratedTimestamp}</span>
              </div>
            )}
          </div>
        </div>

        {/* CONTROLS BAR */}
        <div className="bg-gray-900 border-t border-gray-800 px-4 py-2 flex items-center justify-between text-gray-300 shrink-0">
          
          {/* Left Controls: Play/Pause, Frame Back/Forward, Times */}
          <div className="flex items-center gap-3">
            <button
              onClick={togglePlayPause}
              className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition-colors"
              title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
            >
              {isPlaying ? <Pause size={18} /> : <Play size={18} />}
            </button>

            {/* Frame-by-frame buttons */}
            <button
              onClick={() => stepFrame(-1)}
              disabled={!unifiedVideo.browser_playable}
              className="px-2 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-gray-200 rounded text-xs font-medium flex items-center gap-1 transition-colors"
              title="Previous Frame"
            >
              <ChevronLeft size={16} />
              <span>Frame</span>
            </button>

            <button
              onClick={() => stepFrame(1)}
              disabled={!unifiedVideo.browser_playable}
              className="px-2 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-gray-200 rounded text-xs font-medium flex items-center gap-1 transition-colors"
              title="Next Frame"
            >
              <span>Frame</span>
              <ChevronRight size={16} />
            </button>

            {/* Current Media Time / Duration */}
            <div className="font-mono text-xs text-gray-200 bg-gray-950 px-2.5 py-1 rounded border border-gray-800">
              <span className="text-white font-bold">{formatShortTime(currentTime)}</span>
              <span className="text-gray-500 mx-1">/</span>
              <span className="text-gray-400">{formatShortTime(duration || unifiedVideo.duration_seconds || 0)}</span>
            </div>

            {!unifiedVideo.browser_playable && (
              <span className="text-[11px] text-amber-400/90 italic">
                Frame stepping unavailable for this format.
              </span>
            )}
          </div>

          {/* Right Controls: Playback Speed Selector, Volume, Fullscreen, Frame Export */}
          <div className="flex items-center gap-4">
            
            {/* Speed Selector (ALWAYS VISIBLE DROPDOWN) */}
            <div className="flex items-center gap-1.5 bg-gray-800 border border-gray-700 rounded px-2 py-1">
              <span className="text-[11px] text-gray-400 font-medium">Speed:</span>
              <select
                value={playbackSpeed}
                onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
                className="bg-transparent text-white text-xs font-semibold focus:outline-none cursor-pointer"
              >
                <option value={0.25} className="bg-gray-900 text-white">0.25×</option>
                <option value={0.5} className="bg-gray-900 text-white">0.5×</option>
                <option value={0.75} className="bg-gray-900 text-white">0.75×</option>
                <option value={1.0} className="bg-gray-900 text-white">1×</option>
                <option value={1.25} className="bg-gray-900 text-white">1.25×</option>
                <option value={1.5} className="bg-gray-900 text-white">1.5×</option>
                <option value={2.0} className="bg-gray-900 text-white">2×</option>
                <option value={4.0} className="bg-gray-900 text-white">4×</option>
              </select>
            </div>

            {/* Volume / Mute */}
            <div className="flex items-center gap-1.5">
              <button onClick={toggleMute} className="text-gray-400 hover:text-white p-1">
                {isMuted || volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={isMuted ? 0 : volume}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="w-16 h-1 bg-gray-700 rounded appearance-none cursor-pointer accent-indigo-500"
              />
            </div>

            {/* Fullscreen */}
            <button
              onClick={toggleFullscreen}
              className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-800 transition-colors"
              title="Fullscreen"
            >
              <Maximize2 size={16} />
            </button>

            {/* Export Frame Button */}
            {canEdit && (
              <button
                onClick={handleExportFrame}
                disabled={isExportingFrame || !unifiedVideo.browser_playable}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-colors"
                title="Extract frame as new derived evidence artifact"
              >
                <Camera size={14} />
                {isExportingFrame ? 'Exporting...' : 'Export Frame'}
              </button>
            )}
          </div>
        </div>

        {/* FORENSIC TIMELINE WITH TRACKS */}
        <div className="bg-gray-900/90 border-t border-gray-800 p-3 shrink-0 flex flex-col gap-2">
          
          {/* Timeline Header: Zoom controls, Nav buttons, Synchronization Status */}
          <div className="flex items-center justify-between text-xs text-gray-400">
            <div className="flex items-center gap-3">
              <span className="font-semibold uppercase tracking-wider text-gray-300">Forensic Timeline</span>
              
              {/* Event prev/next buttons */}
              <div className="flex items-center gap-1 bg-gray-800 rounded p-0.5">
                <button
                  onClick={goToPrevEvent}
                  className="px-2 py-0.5 hover:bg-gray-700 rounded text-gray-300 text-[11px] font-medium flex items-center gap-1"
                  title="Previous Event"
                >
                  <ChevronLeft size={12} /> Prev Event
                </button>
                <button
                  onClick={goToNextEvent}
                  className="px-2 py-0.5 hover:bg-gray-700 rounded text-gray-300 text-[11px] font-medium flex items-center gap-1"
                  title="Next Event"
                >
                  Next Event <ChevronRight size={12} />
                </button>
              </div>

              {/* Multi-camera synchronization label */}
              <span className="text-[11px] px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300">
                {unifiedVideo.camera_tracks.length > 1 && unifiedVideo.source_start_time ? (
                  <span className="text-emerald-400 font-medium">Tracks Synchronized ({unifiedVideo.camera_tracks.length} Channels)</span>
                ) : (
                  <span className="text-gray-400">Synchronization: Unavailable</span>
                )}
              </span>
            </div>

            {/* Timeline Zoom Slider / Buttons */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-medium">Zoom:</span>
              {[1, 2, 5, 10].map((z) => (
                <button
                  key={z}
                  onClick={() => setZoomLevel(z)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                    zoomLevel === z ? 'bg-indigo-600 text-white font-bold' : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                  }`}
                >
                  {z}×
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Timeline Track Container (Horizontal Scrolling) */}
          <div className="overflow-x-auto overflow-y-hidden pb-1 custom-scrollbar">
            <div
              style={{ width: `${100 * zoomLevel}%`, minWidth: '100%' }}
              className="relative select-none"
            >
              {/* Time Ruler Ticks */}
              <div className="h-5 w-full border-b border-gray-800 flex items-center justify-between text-[10px] font-mono text-gray-500 px-1 relative">
                <span>00:00:00</span>
                <span>{formatShortTime((duration || 1) * 0.25)}</span>
                <span>{formatShortTime((duration || 1) * 0.5)}</span>
                <span>{formatShortTime((duration || 1) * 0.75)}</span>
                <span>{formatShortTime(duration || 1)}</span>
              </div>

              {/* Camera Channel Tracks */}
              <div
                ref={timelineRef}
                onClick={handleTimelineClick}
                className="relative py-2 space-y-2 cursor-pointer bg-gray-950/60 rounded border border-gray-800/80 p-2"
              >
                {/* Red Playhead Vertical Needle */}
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-red-500 z-30 pointer-events-none"
                  style={{
                    left: `${((currentTime / (duration || 1)) * 100).toFixed(3)}%`,
                  }}
                >
                  <div className="w-2.5 h-2.5 -ml-1 -top-1 absolute bg-red-500 rotate-45" />
                </div>

                {/* Track Rows for CAM 01, CAM 02, etc. */}
                {(unifiedVideo.camera_tracks.length > 0 ? unifiedVideo.camera_tracks : [
                  {
                    channel_number: unifiedVideo.channel_number || 1,
                    channel_name: unifiedVideo.channel_name || 'CAM 01',
                    evidence_id: unifiedVideo.evidence_id,
                    evidence_identifier: unifiedVideo.evidence_identifier,
                    original_filename: unifiedVideo.original_filename,
                    vendor: unifiedVideo.vendor,
                    browser_playable: unifiedVideo.browser_playable,
                    is_active: true,
                    offset_from_master_seconds: 0
                  }
                ]).map((track) => {
                  const effectiveDuration = duration || 1;
                  return (
                    <div
                      key={track.evidence_id}
                      className={`h-8 relative rounded flex items-center px-2 transition-colors ${
                        track.is_active ? 'bg-gray-800/90 border border-indigo-500/60' : 'bg-gray-900/70 border border-gray-800 hover:bg-gray-800/50'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!track.is_active) {
                          setActiveEvidenceId(track.evidence_id);
                        } else {
                          handleTimelineClick(e);
                        }
                      }}
                    >
                      {/* Track Label */}
                      <div className="w-24 shrink-0 font-mono text-[11px] font-bold text-gray-300 flex items-center gap-1.5 z-10 pointer-events-none">
                        <span className={track.is_active ? 'text-indigo-400' : 'text-gray-500'}>
                          {track.channel_name}
                        </span>
                        {track.offset_from_master_seconds !== 0 && (
                          <span className="text-[10px] text-amber-400">
                            ({track.offset_from_master_seconds > 0 ? '+' : ''}{track.offset_from_master_seconds}s)
                          </span>
                        )}
                      </div>

                      {/* Track background bar */}
                      <div className="flex-1 h-2 bg-gray-700/50 rounded-full relative overflow-visible">
                        {/* Event Markers pinned to track if active evidence */}
                        {track.is_active && events.map((ev) => {
                          const posPercent = Math.max(0, Math.min(100, (ev.media_time / effectiveDuration) * 100));
                          return (
                            <div
                              key={ev.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                seekToTime(ev.media_time);
                                setSelectedEventId(ev.id);
                              }}
                              style={{ left: `${posPercent.toFixed(3)}%` }}
                              className={`absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full z-20 cursor-pointer shadow-md transition-transform hover:scale-125 ${
                                selectedEventId === ev.id ? 'ring-2 ring-white scale-125' : ''
                              } ${
                                ev.event_type === 'Incident' ? 'bg-red-500' :
                                ev.event_type === 'Person' ? 'bg-blue-500' :
                                ev.event_type === 'Vehicle' ? 'bg-amber-500' :
                                ev.event_type === 'Entry' || ev.event_type === 'Exit' ? 'bg-emerald-500' :
                                'bg-indigo-400'
                              }`}
                              title={`${ev.event_type}: ${ev.title} (${formatShortTime(ev.media_time)})`}
                            />
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* BOTTOM PANELS: Events / Notes / Calibration / Metadata */}
      <div className="h-56 bg-gray-900 border-t border-gray-800 flex flex-col shrink-0">
        
        {/* Panel Tabs Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-4 shrink-0 bg-gray-900/90">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab('events')}
              className={`px-3 py-2 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === 'events' ? 'border-indigo-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Bookmark size={14} />
              Events ({events.length})
            </button>

            <button
              onClick={() => setActiveTab('notes')}
              className={`px-3 py-2 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === 'notes' ? 'border-indigo-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <FileText size={14} />
              Investigator Notes ({notes.length})
            </button>

            <button
              onClick={() => setActiveTab('calibration')}
              className={`px-3 py-2 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === 'calibration' ? 'border-indigo-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Sliders size={14} />
              Timestamp Calibration {calibration ? '(Active)' : ''}
            </button>

            <button
              onClick={() => setActiveTab('metadata')}
              className={`px-3 py-2 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
                activeTab === 'metadata' ? 'border-indigo-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Info size={14} />
              Technical & Forensic Metadata
            </button>
          </div>

          {/* Tab Actions */}
          <div className="flex items-center gap-2">
            {activeTab === 'events' && canEdit && (
              <button
                onClick={() => setIsAddingEvent(!isAddingEvent)}
                className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium flex items-center gap-1 transition-colors"
              >
                <Plus size={14} /> Add Event at {formatShortTime(currentTime)}
              </button>
            )}
            {activeTab === 'notes' && canEdit && (
              <button
                onClick={() => setIsAddingNote(!isAddingNote)}
                className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-medium flex items-center gap-1 transition-colors"
              >
                <Plus size={14} /> Add Note at {formatShortTime(currentTime)}
              </button>
            )}
          </div>
        </div>

        {/* Tab Content Area */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-950">
          
          {/* TAB 1: EVENTS */}
          {activeTab === 'events' && (
            <div className="space-y-3">
              {/* Event Creation Form */}
              {isAddingEvent && (
                <form onSubmit={handleCreateEvent} className="bg-gray-900 border border-indigo-700/60 rounded-md p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-indigo-300">
                    <span>Create Timeline Event Marker at {formatMediaTime(currentTime)}</span>
                    <button type="button" onClick={() => setIsAddingEvent(false)} className="text-gray-400 hover:text-white">✕</button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <input
                      type="text"
                      placeholder="Event title..."
                      value={newEventTitle}
                      onChange={(e) => setNewEventTitle(e.target.value)}
                      className="md:col-span-2 bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      required
                    />
                    <select
                      value={newEventType}
                      onChange={(e) => setNewEventType(e.target.value)}
                      className="bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500 cursor-pointer"
                    >
                      {['Observation', 'Person', 'Vehicle', 'Object', 'Motion', 'Entry', 'Exit', 'Incident', 'Other'].map(t => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <button
                      type="submit"
                      className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded transition-colors"
                    >
                      Save Marker
                    </button>
                  </div>
                  <textarea
                    placeholder="Optional forensic description or observations..."
                    value={newEventDesc}
                    onChange={(e) => setNewEventDesc(e.target.value)}
                    rows={2}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </form>
              )}

              {/* Event Search Filter */}
              <div className="flex items-center gap-2">
                <div className="relative flex-1 max-w-sm">
                  <Search size={14} className="absolute left-2.5 top-2 text-gray-500" />
                  <input
                    type="text"
                    placeholder="Search events by title, type, description..."
                    value={eventSearch}
                    onChange={(e) => setEventSearch(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded pl-8 pr-2.5 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {/* Event Items List */}
              {events.length === 0 ? (
                <p className="text-xs text-gray-500 py-4 text-center">No timeline event markers recorded yet for this evidence.</p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {events
                    .filter((ev) =>
                      eventSearch ? (
                        ev.title.toLowerCase().includes(eventSearch.toLowerCase()) ||
                        (ev.description && ev.description.toLowerCase().includes(eventSearch.toLowerCase())) ||
                        ev.event_type.toLowerCase().includes(eventSearch.toLowerCase())
                      ) : true
                    )
                    .map((ev) => (
                      <div
                        key={ev.id}
                        onClick={() => {
                          seekToTime(ev.media_time);
                          setSelectedEventId(ev.id);
                        }}
                        className={`bg-gray-900 border ${selectedEventId === ev.id ? 'border-indigo-500 bg-gray-800/80' : 'border-gray-800'} rounded p-2.5 cursor-pointer hover:border-gray-700 transition-colors flex flex-col justify-between`}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="font-bold text-white text-xs truncate">{ev.title}</span>
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-800 text-indigo-300 border border-gray-700">
                              {ev.event_type}
                            </span>
                          </div>
                          {ev.description && (
                            <p className="text-[11px] text-gray-400 line-clamp-2 mb-2">{ev.description}</p>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-[10px] font-mono text-gray-400 pt-1 border-t border-gray-800">
                          <span>Media: {formatShortTime(ev.media_time)}</span>
                          {canEdit && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteEvent(ev.id);
                              }}
                              className="text-gray-500 hover:text-red-400 transition-colors p-1"
                              title="Delete Event"
                            >
                              <Trash2 size={12} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: NOTES */}
          {activeTab === 'notes' && (
            <div className="space-y-3">
              {/* Note Creation Form */}
              {isAddingNote && (
                <form onSubmit={handleCreateNote} className="bg-gray-900 border border-indigo-700/60 rounded-md p-3 space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold text-indigo-300">
                    <span>Add Timestamp-Linked Note at {formatMediaTime(currentTime)}</span>
                    <button type="button" onClick={() => setIsAddingNote(false)} className="text-gray-400 hover:text-white">✕</button>
                  </div>
                  <textarea
                    placeholder="Enter investigator observations linked to this precise timestamp..."
                    value={newNoteText}
                    onChange={(e) => setNewNoteText(e.target.value)}
                    rows={2}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                    required
                  />
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded transition-colors"
                    >
                      Save Note
                    </button>
                  </div>
                </form>
              )}

              {/* Note Search Filter */}
              <div className="flex items-center gap-2">
                <div className="relative flex-1 max-w-sm">
                  <Search size={14} className="absolute left-2.5 top-2 text-gray-500" />
                  <input
                    type="text"
                    placeholder="Search notes..."
                    value={noteSearch}
                    onChange={(e) => setNoteSearch(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-800 rounded pl-8 pr-2.5 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {/* Notes List */}
              {notes.length === 0 ? (
                <p className="text-xs text-gray-500 py-4 text-center">No investigator notes created for this evidence timeline position.</p>
              ) : (
                <div className="space-y-2">
                  {notes
                    .filter((n) => noteSearch ? n.note_text.toLowerCase().includes(noteSearch.toLowerCase()) : true)
                    .map((n) => (
                      <div
                        key={n.id}
                        onClick={() => seekToTime(n.media_time)}
                        className="bg-gray-900 border border-gray-800 rounded p-2.5 flex items-start justify-between gap-3 hover:border-gray-700 cursor-pointer transition-colors"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 font-mono text-[11px]">
                            <span className="text-indigo-400 font-bold">{formatShortTime(n.media_time)}</span>
                            {n.source_timestamp && (
                              <span className="text-emerald-400">CCTV: {n.source_timestamp}</span>
                            )}
                          </div>
                          <p className="text-xs text-gray-200">{n.note_text}</p>
                        </div>
                        {canEdit && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteNote(n.id);
                            }}
                            className="text-gray-500 hover:text-red-400 transition-colors p-1"
                            title="Delete Note"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TIMESTAMP CALIBRATION */}
          {activeTab === 'calibration' && (
            <div className="max-w-xl space-y-3">
              <p className="text-xs text-gray-400">
                Record a known camera clock offset (e.g. against verified external atomic clock reference). This is stored as analysis metadata and <strong>never modifies embedded CCTV timestamps</strong>.
              </p>

              {calibSuccessMsg && (
                <div className="p-2 bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs rounded flex items-center gap-2">
                  <CheckCircle size={14} />
                  {calibSuccessMsg}
                </div>
              )}

              <form onSubmit={handleSaveCalibration} className="bg-gray-900 border border-gray-800 rounded p-3 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-gray-400 block mb-1">Clock Offset (Seconds):</label>
                    <input
                      type="number"
                      step="any"
                      value={calibOffset}
                      onChange={(e) => setCalibOffset(parseFloat(e.target.value) || 0)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                      placeholder="e.g. 192 or -300"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-gray-400 block mb-1">Timezone:</label>
                    <input
                      type="text"
                      value={calibTimezone}
                      onChange={(e) => setCalibTimezone(e.target.value)}
                      className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                      placeholder="UTC or IST (UTC+5:30)"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-gray-400 block mb-1">Calibration Reason / External Reference:</label>
                  <input
                    type="text"
                    value={calibReason}
                    onChange={(e) => setCalibReason(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                    placeholder="Compared against verified external NTP reference or dispatch log"
                  />
                </div>

                {canEdit && (
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition-colors"
                  >
                    Save Calibration Metadata
                  </button>
                )}
              </form>
            </div>
          )}

          {/* TAB 4: METADATA */}
          {activeTab === 'metadata' && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
              <div className="bg-gray-900 border border-gray-800 rounded p-2.5 space-y-1">
                <span className="text-gray-500 text-[10px] block">TECHNICAL MEDIA</span>
                <div>Duration: <span className="text-white">{unifiedVideo.duration_seconds ? `${unifiedVideo.duration_seconds.toFixed(2)}s` : 'Unknown'}</span></div>
                <div>Resolution: <span className="text-white">{unifiedVideo.width && unifiedVideo.height ? `${unifiedVideo.width}x${unifiedVideo.height}` : 'Unknown'}</span></div>
                <div>FPS: <span className="text-white">{unifiedVideo.fps}</span></div>
                <div>Bitrate: <span className="text-white">{unifiedVideo.bitrate_kbps ? `${unifiedVideo.bitrate_kbps} kbps` : 'Unknown'}</span></div>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded p-2.5 space-y-1">
                <span className="text-gray-500 text-[10px] block">CODECS & CONTAINER</span>
                <div>Video Codec: <span className="text-indigo-300">{unifiedVideo.video_codec || 'Standard'}</span></div>
                <div>Audio Codec: <span className="text-indigo-300">{unifiedVideo.audio_codec || 'None'}</span></div>
                <div>Format: <span className="text-white">{unifiedVideo.container_format}</span></div>
                <div>Vendor: <span className="text-amber-300">{unifiedVideo.vendor}</span></div>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded p-2.5 space-y-1">
                <span className="text-gray-500 text-[10px] block">PROVENANCE</span>
                <div>Device ID: <span className="text-white">{unifiedVideo.source_device_identifier || 'Not available'}</span></div>
                <div>Acquisition ID: <span className="text-white">{unifiedVideo.acquisition_identifier || 'Not available'}</span></div>
                <div>Channel: <span className="text-white">CAM {unifiedVideo.channel_number}</span></div>
                <div>Lineage: <span className={unifiedVideo.is_inspection_proxy ? 'text-purple-400' : 'text-emerald-400'}>
                  {unifiedVideo.is_inspection_proxy ? 'DERIVED INSPECTION PROXY' : 'ORIGINAL'}
                </span></div>
              </div>

              <div className="bg-gray-900 border border-gray-800 rounded p-2.5 space-y-1">
                <span className="text-gray-500 text-[10px] block">FORENSIC INTEGRITY</span>
                <div className="flex items-center justify-between">
                  <span className="truncate max-w-[140px] text-[10px] text-gray-300">SHA-256: {unifiedVideo.sha256 ? `${unifiedVideo.sha256.slice(0, 10)}...` : 'N/A'}</span>
                  {unifiedVideo.sha256 && (
                    <button
                      onClick={() => copyHash(unifiedVideo.sha256 || '', 'sha')}
                      className="text-gray-400 hover:text-white p-0.5"
                      title="Copy SHA-256"
                    >
                      <Copy size={11} />
                    </button>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <span className="truncate max-w-[140px] text-[10px] text-gray-300">MD5: {unifiedVideo.md5_reference ? `${unifiedVideo.md5_reference.slice(0, 10)}...` : 'N/A'}</span>
                  {unifiedVideo.md5_reference && (
                    <button
                      onClick={() => copyHash(unifiedVideo.md5_reference || '', 'md5')}
                      className="text-gray-400 hover:text-white p-0.5"
                      title="Copy MD5"
                    >
                      <Copy size={11} />
                    </button>
                  )}
                </div>
                {copiedHash && (
                  <span className="text-[10px] text-emerald-400 font-sans">Copied to clipboard!</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* EXPORTED FRAME SUCCESS MODAL */}
      {exportedFrame && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-emerald-700/70 rounded-lg max-w-md w-full p-5 space-y-4 shadow-2xl text-xs">
            <div className="flex items-center justify-between text-emerald-400 font-bold text-sm">
              <span className="flex items-center gap-2">
                <CheckCircle size={18} /> Frame Exported Successfully
              </span>
              <button onClick={() => setExportedFrame(null)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            
            <p className="text-gray-300">
              A new <strong>DERIVED</strong> forensic artifact has been generated. The original evidence remains completely unmodified.
            </p>

            <div className="bg-gray-950 border border-gray-800 rounded p-3 space-y-2 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-gray-400">New Evidence ID:</span>
                <span className="text-indigo-300 font-bold">{exportedFrame.evidence_identifier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Parent Evidence ID:</span>
                <span className="text-amber-300">{exportedFrame.parent_evidence_identifier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Operation:</span>
                <span className="text-purple-400 font-bold">{exportedFrame.derived_operation}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Media Time:</span>
                <span className="text-white">{formatMediaTime(exportedFrame.media_time)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Frame Number:</span>
                <span className="text-white">{exportedFrame.frame_number}</span>
              </div>
              <div className="border-t border-gray-800 pt-1">
                <div className="text-gray-400 mb-0.5">SHA-256 Hash:</div>
                <div className="text-[10px] text-emerald-400 break-all select-all">{exportedFrame.sha256}</div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setExportedFrame(null)}
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded font-medium"
              >
                Close
              </button>
              <button
                onClick={() => {
                  setExportedFrame(null);
                  navigate(`/case/${caseId}/evidence/${exportedFrame.evidence_id}`);
                }}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded font-semibold flex items-center gap-1.5"
              >
                <ExternalLink size={13} /> View Derived Artifact
              </button>
            </div>
          </div>
        </div>
      )}

      {/* HEX PREVIEW MODAL */}
      {isHexPreviewOpen && (
        <HexPreviewModal
          isOpen={isHexPreviewOpen}
          caseId={activeCase?.case_identifier || caseId || ''}
          evidenceId={unifiedVideo.evidence_id}
          evidenceIdentifier={unifiedVideo.evidence_identifier}
          filename={unifiedVideo.original_filename}
          onClose={() => setIsHexPreviewOpen(false)}
        />
      )}
    </div>
  );
}
