import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ArrowLeft, Shield, CheckCircle, AlertOctagon, 
  Copy, PlayCircle, Image as ImageIcon, MapPin, File as FileIcon,
  Film, GitBranch, ArrowDown, ExternalLink, Info, Cpu
} from 'lucide-react';
import { evidenceService } from '../../../services/evidenceService';
import type { Evidence } from '../../../services/evidenceService';
import { useAuth } from '../../../hooks/useAuth';
import { Badge } from '../../ui/Badge';
import { CreateDerivedClipModal } from './CreateDerivedClipModal';

export function EvidenceInspectionView() {
  const { caseId, evidenceId } = useParams();
  const { activeCase, role } = useAuth();
  const navigate = useNavigate();

  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [copiedHash, setCopiedHash] = useState<'sha256' | 'md5' | null>(null);

  // Derivation modal state
  const [isDerivedModalOpen, setIsDerivedModalOpen] = useState(false);

  // Video Metadata
  const videoRef = useRef<HTMLVideoElement>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [videoDuration, setVideoDuration] = useState<number | null>(null);
  const [videoResolution, setVideoResolution] = useState<{w: number, h: number} | null>(null);

  const canVerify = role === 'ADMIN' || role === 'INVESTIGATOR';
  const canDerive = (role === 'ADMIN' || role === 'INVESTIGATOR') && evidence?.media_type === 'Video';

  useEffect(() => {
    if (!caseId || !evidenceId) return;

    const loadEvidence = async () => {
      setIsLoading(true);
      try {
        const data = await evidenceService.getEvidence(activeCase?.case_identifier || caseId, parseInt(evidenceId));
        setEvidence(data);
      } catch (err) {
        setError('Failed to load evidence details.');
      } finally {
        setIsLoading(false);
      }
    };

    loadEvidence();
  }, [caseId, evidenceId, activeCase]);

  const handleVerify = async () => {
    if (!evidence || !caseId) return;
    
    setIsVerifying(true);
    setError(null);
    try {
      const response = await evidenceService.verifyEvidence(activeCase?.case_identifier || caseId, evidence.id);
      setEvidence(prev => prev ? {
        ...prev,
        integrity_status: response.result as any,
        sha256: response.actual_sha256,
        stored_sha256: response.expected_sha256
      } : null);
    } catch (err) {
      setError('Verification failed to execute properly.');
    } finally {
      setIsVerifying(false);
    }
  };

  const copyToClipboard = (text: string, type: 'sha256' | 'md5') => {
    navigator.clipboard.writeText(text);
    setCopiedHash(type);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setVideoDuration(videoRef.current.duration);
      setVideoResolution({
        w: videoRef.current.videoWidth,
        h: videoRef.current.videoHeight
      });
    }
  };

  const handleSpeedChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const speed = parseFloat(e.target.value);
    setPlaybackSpeed(speed);
    if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
  };

  const formatSize = (bytes: number) => {
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatDuration = (seconds: number) => {
    if (!isFinite(seconds)) return 'Not available';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  // Parse derived parameters if present
  let parsedParams: any = null;
  if (evidence?.derived_parameters) {
    try {
      parsedParams = JSON.parse(evidence.derived_parameters);
    } catch (e) {
      parsedParams = null;
    }
  }

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!evidence) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-4">
        <AlertOctagon size={48} className="text-gray-300" />
        <p className="text-lg font-medium text-gray-900">Evidence not found</p>
        <button 
          onClick={() => navigate(`/case/${caseId}/evidence`)}
          className="text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-2"
        >
          <ArrowLeft size={16} /> Back to Evidence
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-50">
      
      {/* Header */}
      <header className="bg-white px-6 py-4 border-b border-gray-200 flex items-center justify-between shadow-sm shrink-0">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate(`/case/${caseId}/evidence`)}
            className="p-2 -ml-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
            title="Back to Evidence"
          >
            <ArrowLeft size={20} />
          </button>
          <div className="h-6 w-px bg-gray-200"></div>
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                {evidence.evidence_identifier}
              </span>
              <h1 className="text-lg font-bold text-gray-900 line-clamp-1">{evidence.original_filename}</h1>
              {evidence.evidence_status === 'DERIVED' ? (
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200">
                  Derived
                </span>
              ) : (
                <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                  Original
                </span>
              )}
            </div>
          </div>
        </div>

        {canDerive && (
          <button
            onClick={() => setIsDerivedModalOpen(true)}
            className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-sm transition-colors flex items-center gap-2"
          >
            <Film size={15} />
            Create Derived Clip
          </button>
        )}
      </header>

      {/* Main Workspace (Two-Column Layout) */}
      <div className="flex-1 overflow-hidden grid" style={{ gridTemplateColumns: "minmax(0, 1.2fr) minmax(420px, 1fr)" }}>
        
        {/* LEFT COLUMN: Playback / Inspection */}
        <div className="bg-gray-900 flex flex-col relative overflow-hidden border-r border-gray-800">
          <div className="p-4 bg-gray-900 border-b border-gray-800 flex items-center justify-between text-gray-300">
            <h2 className="text-xs font-semibold uppercase tracking-wider flex items-center gap-2">
              {evidence.media_type === 'Video' ? <PlayCircle size={16} /> : <ImageIcon size={16} />}
              Forensic Playback
            </h2>
            
            {/* Playback Controls & Speed */}
            {evidence.media_type === 'Video' && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <label htmlFor="playback-speed" className="text-xs font-medium">Speed:</label>
                  <select 
                    id="playback-speed"
                    value={playbackSpeed}
                    onChange={handleSpeedChange}
                    className="bg-gray-800 border border-gray-700 text-white text-xs rounded px-2 py-1 focus:outline-none focus:border-indigo-500 cursor-pointer"
                  >
                    <option value={0.25}>0.25×</option>
                    <option value={0.5}>0.5×</option>
                    <option value={0.75}>0.75×</option>
                    <option value={1}>1×</option>
                    <option value={1.25}>1.25×</option>
                    <option value={1.5}>1.5×</option>
                    <option value={2}>2×</option>
                    <option value={4}>4×</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          <div className="flex-1 flex items-center justify-center p-6 bg-black overflow-hidden relative">
            {evidence.media_type === 'Video' ? (
              <video 
                ref={videoRef}
                controls 
                preload="metadata"
                onLoadedMetadata={handleLoadedMetadata}
                className="w-full max-h-[60vh] aspect-video object-contain outline-none shadow-2xl"
                src={`/api/v1/cases/${activeCase?.case_identifier}/evidence/${evidence.id}/stream?access_token=${localStorage.getItem('drishtik_token')}`}
              >
                Preview unavailable for this format
              </video>
            ) : evidence.media_type === 'Image' ? (
              <img 
                className="max-w-full max-h-full object-contain shadow-2xl"
                src={`/api/v1/cases/${activeCase?.case_identifier}/evidence/${evidence.id}/stream?access_token=${localStorage.getItem('drishtik_token')}`}
                alt={evidence.original_filename}
              />
            ) : (
              <div className="text-gray-500 flex flex-col items-center gap-2">
                <FileIcon size={48} className="opacity-50" />
                <p>Preview unavailable for this format</p>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Metadata & Integrity */}
        <div className="bg-white flex flex-col overflow-y-auto h-full">
          <div className="p-6 bg-white border-b border-gray-100 sticky top-0 z-10 shrink-0">
            <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Evidence Information</h2>
          </div>
          <div className="p-6 space-y-8">
            
            {error && (
              <div className="p-4 bg-red-50 text-red-700 text-sm rounded-md border border-red-100 flex items-start gap-2 shadow-sm">
                <AlertOctagon size={18} className="mt-0.5 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            {/* FORENSIC LINEAGE (If Derived) */}
            {evidence.evidence_status === 'DERIVED' && (
              <section className="bg-purple-50/60 p-4 rounded-xl border border-purple-200">
                <h3 className="text-xs font-bold text-purple-950 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <GitBranch size={14} className="text-purple-700" />
                  Forensic Evidence Lineage
                </h3>
                
                {/* Parent Node */}
                <div className="bg-white p-3 rounded-lg border border-purple-200 shadow-sm flex items-center justify-between">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-purple-600">Original Parent Evidence</div>
                    <div className="font-mono text-xs font-bold text-gray-900 mt-0.5">
                      {evidence.parent_evidence_identifier || `Parent ID: ${evidence.parent_evidence_id}`}
                    </div>
                    <div className="text-xs text-gray-600 truncate max-w-[240px]">
                      {evidence.parent_filename || 'Original Source File'}
                    </div>
                  </div>
                  {evidence.parent_evidence_id && (
                    <button
                      onClick={() => navigate(`/case/${caseId}/evidence/${evidence.parent_evidence_id}`)}
                      className="px-2.5 py-1.5 text-xs font-semibold text-purple-700 bg-purple-100/70 hover:bg-purple-200 rounded-md transition-colors flex items-center gap-1 shrink-0"
                    >
                      <ExternalLink size={12} /> View Parent
                    </button>
                  )}
                </div>

                <div className="flex justify-center my-1.5">
                  <ArrowDown size={16} className="text-purple-400" />
                </div>

                {/* Child Node (Current) */}
                <div className="bg-white p-3 rounded-lg border-2 border-purple-500 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-purple-700">Derived Evidence (Current)</span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-100 text-purple-800">
                      {evidence.derived_operation}
                    </span>
                  </div>
                  <div className="font-mono text-xs font-bold text-gray-900 mt-0.5">
                    {evidence.evidence_identifier}
                  </div>
                  <div className="text-xs text-gray-600 truncate">
                    {evidence.original_filename}
                  </div>
                </div>

                {/* Derivation Parameters Summary */}
                {parsedParams && (
                  <div className="mt-3 pt-3 border-t border-purple-200 text-xs text-purple-950 space-y-1">
                    <div className="font-semibold text-[11px] uppercase tracking-wider text-purple-800">
                      Derivation Parameters:
                    </div>
                    {parsedParams.start_time !== undefined && parsedParams.end_time !== undefined && (
                      <div>
                        <strong>Trim Range:</strong> {parsedParams.start_time}s to {parsedParams.end_time}s ({Math.max(0, parsedParams.end_time - parsedParams.start_time).toFixed(2)}s duration)
                      </div>
                    )}
                    {parsedParams.crop && (
                      <div>
                        <strong>Crop Region:</strong> {parsedParams.crop.width} × {parsedParams.crop.height} px (X: {parsedParams.crop.x}, Y: {parsedParams.crop.y})
                      </div>
                    )}
                  </div>
                )}
              </section>
            )}

            {/* ORIGINAL REPOSITORY PROVENANCE (If Original) */}
            {evidence.evidence_status === 'ORIGINAL' && (
              <section className="bg-emerald-50/50 p-3.5 rounded-lg border border-emerald-200 text-xs text-emerald-950 flex items-start gap-2.5">
                <Info size={16} className="text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-emerald-900">Original Evidence Repository Provenance</div>
                  <p className="text-emerald-800 mt-0.5">
                    Original as imported into this case. This denotes repository provenance and does not independently establish the authenticity of the source recording.
                  </p>
                  {(evidence.active_derived_children_count ?? 0) > 0 && (
                    <div className="mt-2 font-semibold text-emerald-900 flex items-center gap-1.5">
                      <GitBranch size={13} />
                      This original evidence has {evidence.active_derived_children_count} derived child clip(s).
                    </div>
                  )}
                </div>
              </section>
            )}

            
            {/* FORENSIC ACQUISITION PROVENANCE */}
            {(evidence.source_type === 'Acquired' || evidence.acquisition_identifier) && (
              <section className="bg-blue-50/60 p-4 rounded-xl border border-blue-200 text-xs text-blue-950 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-bold text-blue-900 text-sm">
                    <Cpu size={16} className="text-blue-600" />
                    <span>Forensic Acquisition Provenance</span>
                  </div>
                  <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                    ACQUIRED
                  </span>
                </div>
                <p className="text-blue-800 text-xs">
                  This evidence originated directly from a verifiable read-only forensic hardware acquisition.
                </p>
                <div className="grid grid-cols-2 gap-3 pt-2 border-t border-blue-200/60 text-xs">
                  <div>
                    <span className="text-blue-600 font-semibold block text-[10px]">Source Device</span>
                    {evidence.device_identifier ? (
                      <Link
                        to={`/case/${caseId}/devices/${evidence.device_identifier}`}
                        className="font-mono font-bold text-indigo-600 hover:text-indigo-800 underline flex items-center gap-1"
                      >
                        {evidence.device_identifier}
                        <ExternalLink size={11} />
                      </Link>
                    ) : (
                      <span className="text-gray-500">Not recorded</span>
                    )}
                    {evidence.device_manufacturer && (
                      <span className="text-blue-900 block text-[11px]">{evidence.device_manufacturer} {evidence.device_model || ''}</span>
                    )}
                  </div>
                  <div>
                    <span className="text-blue-600 font-semibold block text-[10px]">Acquisition Record</span>
                    <span className="font-mono font-bold text-gray-900">
                      {evidence.acquisition_identifier || 'Recorded'}
                    </span>
                    {evidence.acquisition_method && (
                      <span className="text-blue-900 block text-[11px]">{evidence.acquisition_method}</span>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* FILE INFORMATION */}
            <section>
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2">File Information</h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                <div>
                  <dt className="text-gray-500 mb-1">File Name</dt>
                  <dd className="font-medium text-gray-900 break-words">{evidence.original_filename}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Evidence ID</dt>
                  <dd className="font-mono text-gray-900 bg-gray-100 px-1.5 py-0.5 rounded inline-block">{evidence.evidence_identifier}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">File Size</dt>
                  <dd className="font-medium text-gray-900">{formatSize(evidence.size_bytes)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Format</dt>
                  <dd className="font-medium text-gray-900">{evidence.file_extension.toUpperCase()}</dd>
                </div>
              </dl>
            </section>

            {/* MEDIA INFORMATION */}
            {evidence.media_type === 'Video' && (
              <section>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2">Media Information</h3>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                  <div>
                    <dt className="text-gray-500 mb-1">Duration</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.duration_seconds ? formatDuration(evidence.duration_seconds) : (videoDuration ? formatDuration(videoDuration) : 'Not available')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 mb-1">Resolution</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.width && evidence.height ? `${evidence.width} × ${evidence.height}` : (videoResolution ? `${videoResolution.w} × ${videoResolution.h}` : 'Not available')}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 mb-1">Frame Rate</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.fps ? `${evidence.fps} FPS` : 'Not available'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 mb-1">Video Codec</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.video_codec || 'Not available'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 mb-1">Audio Codec</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.audio_codec || 'Not available'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 mb-1">Bitrate</dt>
                    <dd className="font-medium text-gray-900">
                      {evidence.bitrate_kbps ? `${evidence.bitrate_kbps} kb/s` : 'Not available'}
                    </dd>
                  </div>
                </dl>
              </section>
            )}

            {/* INTEGRITY */}
            <section>
              <div className="flex items-center justify-between mb-4 border-b border-gray-100 pb-2">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Integrity</h3>
                {canVerify && (
                  <button 
                    onClick={handleVerify}
                    disabled={isVerifying}
                    className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded transition-colors disabled:opacity-50"
                  >
                    <Shield size={14} />
                    {isVerifying ? 'Verifying...' : 'Verify Integrity'}
                  </button>
                )}
              </div>
              
              <div className={`p-4 rounded-md border mb-4 ${
                evidence.integrity_status === 'VERIFIED' ? 'bg-emerald-50 border-emerald-200' :
                evidence.integrity_status === 'MISMATCH' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  {evidence.integrity_status === 'VERIFIED' ? <CheckCircle className="text-emerald-600" size={16} /> :
                   evidence.integrity_status === 'MISMATCH' ? <AlertOctagon className="text-red-600" size={16} /> :
                   <Shield className="text-gray-400" size={16} />}
                  <span className={`font-bold ${
                    evidence.integrity_status === 'VERIFIED' ? 'text-emerald-800' :
                    evidence.integrity_status === 'MISMATCH' ? 'text-red-800' : 'text-gray-700'
                  }`}>
                    {evidence.integrity_status}
                  </span>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-end mb-1">
                    <p className="text-xs font-semibold text-gray-700 flex items-center gap-2">
                      SHA-256 (Primary)
                      {evidence.sha256 === evidence.stored_sha256 && evidence.sha256 ? (
                        <span className="text-emerald-600 text-[10px] uppercase font-bold bg-emerald-100 px-1.5 py-0.5 rounded">Matches</span>
                      ) : evidence.stored_sha256 ? (
                        <span className="text-red-600 text-[10px] uppercase font-bold bg-red-100 px-1.5 py-0.5 rounded">Differs</span>
                      ) : null}
                    </p>
                    {evidence.sha256 && (
                      <button 
                        onClick={() => copyToClipboard(evidence.sha256!, 'sha256')}
                        className="text-gray-500 hover:text-indigo-600 transition-colors flex items-center gap-1 text-[11px] font-medium bg-gray-100 hover:bg-indigo-50 px-2 py-0.5 rounded"
                      >
                        {copiedHash === 'sha256' ? <span className="text-emerald-600">Copied!</span> : <><Copy size={12} /> Copy</>}
                      </button>
                    )}
                  </div>
                  <div className="bg-gray-50 p-2.5 rounded border border-gray-200 font-mono text-[12px] text-gray-800 break-all">
                    {evidence.sha256 || <span className="text-gray-400 italic font-sans">Not available</span>}
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-end mb-1">
                    <p className="text-xs font-semibold text-gray-700">MD5 (Reference)</p>
                    {evidence.md5_reference && (
                      <button 
                        onClick={() => copyToClipboard(evidence.md5_reference!, 'md5')}
                        className="text-gray-500 hover:text-indigo-600 transition-colors flex items-center gap-1 text-[11px] font-medium bg-gray-100 hover:bg-indigo-50 px-2 py-0.5 rounded"
                      >
                        {copiedHash === 'md5' ? <span className="text-emerald-600">Copied!</span> : <><Copy size={12} /> Copy</>}
                      </button>
                    )}
                  </div>
                  <div className="bg-gray-50 p-2.5 rounded border border-gray-200 font-mono text-[12px] text-gray-800 break-all">
                    {evidence.md5_reference || <span className="text-gray-400 italic font-sans">Not available</span>}
                  </div>
                </div>
              </div>
            </section>

            {/* SOURCE & PROCESSING */}
            <section>
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2">Source & Processing</h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                <div>
                  <dt className="text-gray-500 mb-1">Source Type</dt>
                  <dd className="font-medium text-gray-900">{evidence.source_type}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Processing Status</dt>
                  <dd className="font-medium text-gray-900">{evidence.processing_status}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Import Date</dt>
                  <dd className="font-medium text-gray-900">{formatDate(evidence.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500 mb-1">Evidence Status</dt>
                  <dd className="mt-0.5">
                    <Badge variant={evidence.evidence_status === 'ORIGINAL' ? 'active' : 'default'}>
                      {evidence.evidence_status}
                    </Badge>
                  </dd>
                </div>
              </dl>
            </section>

            {/* LOCATION */}
            <section>
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4 border-b border-gray-100 pb-2 flex items-center gap-1.5">
                <MapPin size={14} /> Recorded Location
              </h3>
              {evidence.evidence_status === 'DERIVED' && evidence.parent_evidence_identifier ? (
                <p className="text-sm text-gray-500 italic">Inherited from parent evidence ({evidence.parent_evidence_identifier}) - Not available from source</p>
              ) : (
                <p className="text-sm text-gray-500 italic">Not available from evidence metadata</p>
              )}
            </section>

          </div>
        </div>
      </div>

      {/* Derived Evidence Creation Modal */}
      {isDerivedModalOpen && (
        <CreateDerivedClipModal
          isOpen={isDerivedModalOpen}
          onClose={() => setIsDerivedModalOpen(false)}
          evidence={evidence}
          caseIdentifier={activeCase?.case_identifier || caseId || ''}
          onDerivedCreated={(derived) => {
            navigate(`/case/${caseId}/evidence/${derived.id}`);
          }}
        />
      )}
    </div>
  );
}
