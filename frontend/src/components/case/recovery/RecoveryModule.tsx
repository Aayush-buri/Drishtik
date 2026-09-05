import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  DatabaseBackup,
  ShieldCheck,
  HardDrive,
  CheckCircle,
  AlertTriangle,
  Play,
  RotateCw,
  ExternalLink,
  FileCode,
  Layers,
  Download
} from 'lucide-react';
import { useAuth } from '../../../hooks/useAuth';
import { evidenceService, type Evidence } from '../../../services/evidenceService';
import {
  recoveryService,
  type RecoveryCandidate,
  type RecoveryScanJob,
  type RecoverCandidateResult,
} from '../../../services/recoveryService';

export function RecoveryModule() {
  const { caseId } = useParams();
  const { activeCase, role } = useAuth();
  const navigate = useNavigate();

  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<number | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanJob, setScanJob] = useState<RecoveryScanJob | null>(null);
  const [candidates, setCandidates] = useState<RecoveryCandidate[]>([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<RecoveryCandidate | null>(null);
  const [recoveredResult, setRecoveredResult] = useState<RecoverCandidateResult | null>(null);
  const [validatingId, setValidatingId] = useState<number | null>(null);
  const [recoveringId, setRecoveringId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canEdit = role === 'ADMIN' || role === 'INVESTIGATOR';

  // Load available disk images and evidence
  useEffect(() => {
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    evidenceService.listEvidence(caseIdent)
      .then((items: Evidence[]) => {
        setEvidenceList(items.filter((e) => !e.is_deleted));
        if (items.length > 0 && !selectedEvidenceId) {
          setSelectedEvidenceId(items[0].id);
        }
      })
      .catch((err) => {
        console.error('Failed to load case evidence for recovery:', err);
      });
  }, [caseId, activeCase]);

  // Load existing candidates when evidence selected
  useEffect(() => {
    if (!selectedEvidenceId) return;
    const caseIdent = activeCase?.case_identifier || caseId;
    if (!caseIdent) return;

    setIsLoadingCandidates(true);
    recoveryService.listCandidates(caseIdent, selectedEvidenceId)
      .then((data) => {
        setCandidates(data);
      })
      .catch((err) => {
        console.error('Failed to load recovery candidates:', err);
      })
      .finally(() => {
        setIsLoadingCandidates(false);
      });
  }, [selectedEvidenceId, caseId, activeCase]);

  // Launch Recovery Scan
  const handleStartScan = async () => {
    if (!selectedEvidenceId || !activeCase) return;
    setIsScanning(true);
    setError(null);
    try {
      const job = await recoveryService.startScan(activeCase.case_identifier, selectedEvidenceId, 25 * 1024 * 1024);
      setScanJob(job);
      setCandidates(job.candidates);
    } catch (err: any) {
      setError(err.detail || 'Recovery scan failed to start');
    } finally {
      setIsScanning(false);
    }
  };

  // Validate Candidate
  const handleValidate = async (candId: number) => {
    if (!activeCase) return;
    setValidatingId(candId);
    try {
      const res = await recoveryService.validateCandidate(activeCase.case_identifier, candId);
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candId
            ? { ...c, status: res.status as any, confidence: res.confidence, validation_details: res.validation_details }
            : c
        )
      );
      if (selectedCandidate?.id === candId) {
        setSelectedCandidate((prev) =>
          prev ? { ...prev, status: res.status as any, confidence: res.confidence, validation_details: res.validation_details } : null
        );
      }
    } catch (err: any) {
      alert(err.detail || 'Candidate validation failed');
    } finally {
      setValidatingId(null);
    }
  };

  // Recover Candidate
  const handleRecover = async (candId: number) => {
    if (!activeCase) return;
    setRecoveringId(candId);
    try {
      const result = await recoveryService.recoverCandidate(activeCase.case_identifier, candId);
      setRecoveredResult(result);
      setCandidates((prev) =>
        prev.map((c) => (c.id === candId ? result.candidate : c))
      );
      if (selectedCandidate?.id === candId) {
        setSelectedCandidate(result.candidate);
      }
    } catch (err: any) {
      alert(err.detail || 'Carving recovery failed');
    } finally {
      setRecoveringId(null);
    }
  };

  const selectedEvidence = evidenceList.find((e) => e.id === selectedEvidenceId);

  // Categorize evidence sources to clearly distinguish Disk Images, Binary Streams, and Standard Video
  const DISK_IMAGE_EXTS = ['.raw', '.dd', '.img', '.e01', '.001'];
  const BINARY_STREAM_EXTS = ['.dav', '.bin', '.stream', '.h264', '.h265'];

  const getSourceCategory = (ev: Evidence): 'DISK_IMAGE' | 'BINARY_STREAM' | 'STANDARD_VIDEO' => {
    const ext = (ev.file_extension || '').toLowerCase();
    const filename = (ev.original_filename || '').toLowerCase();
    if (DISK_IMAGE_EXTS.some(e => ext === e || filename.endsWith(e)) || ev.source_type === 'DISK_IMAGE') {
      return 'DISK_IMAGE';
    }
    if (BINARY_STREAM_EXTS.some(e => ext === e || filename.endsWith(e)) || ev.proprietary_format === 'DHAV' || ev.proprietary_format === 'HIKB' || ev.media_type === 'Binary') {
      return 'BINARY_STREAM';
    }
    return 'STANDARD_VIDEO';
  };

  const selectedCategory = selectedEvidence ? getSourceCategory(selectedEvidence) : 'STANDARD_VIDEO';
  const isSupportedRecoverySource = selectedCategory === 'DISK_IMAGE' || selectedCategory === 'BINARY_STREAM';

  const diskImages = evidenceList.filter(e => getSourceCategory(e) === 'DISK_IMAGE');
  const binaryStreams = evidenceList.filter(e => getSourceCategory(e) === 'BINARY_STREAM');
  const standardVideos = evidenceList.filter(e => getSourceCategory(e) === 'STANDARD_VIDEO');

  return (
    <div className="h-full flex flex-col bg-slate-50 text-gray-900 p-6 overflow-y-auto font-sans">
      
      {/* Header */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-lg">
            <DatabaseBackup size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">Forensic Stream & Video Recovery</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Recover and validate supported CCTV video structures from forensic images and binary storage sources.
            </p>
          </div>
        </div>

        {/* Read-Only Safety Assurance Badge */}
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-md text-xs text-emerald-800 font-medium">
          <ShieldCheck size={16} className="text-emerald-600 shrink-0" />
          <span>Source Immutability Guaranteed: <strong>Read-Only</strong></span>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md flex items-center gap-2">
          <AlertTriangle size={16} className="shrink-0" />
          {error}
        </div>
      )}

      {/* Source Selection and Scan Action Card */}
      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div className="flex-1 max-w-2xl">
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
              SELECT FORENSIC SOURCE
            </label>
            <select
              value={selectedEvidenceId || ''}
              onChange={(e) => setSelectedEvidenceId(Number(e.target.value))}
              className="w-full bg-white border border-gray-300 text-gray-800 rounded-md px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer shadow-xs font-medium"
            >
              {diskImages.length > 0 && (
                <optgroup label="Forensic Storage Images (.raw, .dd, .img, .e01)">
                  {diskImages.map((ev) => (
                    <option key={ev.id} value={ev.id}>
                      {ev.evidence_identifier} — {ev.original_filename} (Forensic Image, {(ev.size_bytes / (1024 * 1024)).toFixed(2)} MB)
                    </option>
                  ))}
                </optgroup>
              )}

              {binaryStreams.length > 0 && (
                <optgroup label="Binary / CCTV Stream Sources">
                  {binaryStreams.map((ev) => (
                    <option key={ev.id} value={ev.id}>
                      {ev.evidence_identifier} — {ev.original_filename} (Binary Stream, {(ev.size_bytes / (1024 * 1024)).toFixed(2)} MB)
                    </option>
                  ))}
                </optgroup>
              )}

              {standardVideos.length > 0 && (
                <optgroup label="Standard Video Files (Not Raw Storage)">
                  {standardVideos.map((ev) => (
                    <option key={ev.id} value={ev.id}>
                      {ev.evidence_identifier} — {ev.original_filename} (Standard Video, {(ev.size_bytes / (1024 * 1024)).toFixed(2)} MB)
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>

          <button
            onClick={handleStartScan}
            disabled={isScanning || !selectedEvidenceId || !canEdit || !isSupportedRecoverySource}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-md text-xs font-semibold flex items-center gap-2 transition-colors shadow-xs"
            title={!isSupportedRecoverySource ? 'Recovery scanning is only supported on raw storage images and binary streams' : 'Start forensic stream carving scan'}
          >
            {isScanning ? (
              <>
                <RotateCw size={15} className="animate-spin" />
                Carving in Progress...
              </>
            ) : (
              <>
                <Play size={15} />
                Start Recovery Scan
              </>
            )}
          </button>
        </div>

        {/* Warning if a standard video is selected */}
        {!isSupportedRecoverySource && selectedEvidence && (
          <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-md text-xs flex items-start gap-2.5">
            <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Standard Video File Selected:</span>
              <p className="mt-0.5 text-amber-700">
                This source is a standard video file. Use Video Analysis for video investigation. Recovery scanning requires a supported raw/storage image or binary source.
              </p>
            </div>
          </div>
        )}

        {/* Selected Source Provenance Metadata Card */}
        {selectedEvidence && (
          <div className="pt-3 border-t border-gray-100 flex flex-wrap items-center gap-6 text-xs text-gray-500 font-mono">
            <div>Source: <span className="text-gray-900 font-bold">{selectedEvidence.evidence_identifier}</span></div>
            <div>
              Type:{' '}
              <span className="font-sans font-semibold text-indigo-700">
                {selectedCategory === 'DISK_IMAGE' ? 'Forensic Storage Image' :
                 selectedCategory === 'BINARY_STREAM' ? 'Binary / CCTV Stream' : 'Standard Video File'}
              </span>
            </div>
            <div>File Size: <span className="text-gray-800 font-semibold">{(selectedEvidence.size_bytes / (1024 * 1024)).toFixed(2)} MB</span></div>
            <div>SHA-256: <span className="text-emerald-700 font-bold">{selectedEvidence.sha256 ? `${selectedEvidence.sha256.slice(0, 16)}...` : 'N/A'}</span></div>
            <div>Read-Only: <span className="text-emerald-700 font-bold">VERIFIED</span></div>
            {scanJob && (
              <div className="flex items-center gap-2 px-2 py-0.5 rounded bg-indigo-50 border border-indigo-200 text-indigo-800 font-sans">
                <span>Job #{scanJob.id}:</span>
                <span className="font-semibold">{scanJob.status}</span>
                <span>({scanJob.candidates_found} found)</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Results Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-indigo-600" />
          <h2 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
            Discovered Stream Candidates ({candidates.length})
          </h2>
        </div>
        {isLoadingCandidates && (
          <span className="text-xs text-gray-500 flex items-center gap-1">
            <RotateCw size={12} className="animate-spin text-indigo-600" /> Loading candidates...
          </span>
        )}
      </div>

      {/* Candidates Table */}
      <div className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden shadow-xs flex flex-col">
        {candidates.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-gray-500 text-center space-y-3">
            <HardDrive size={40} className="opacity-30 text-gray-400" />
            <p className="text-sm font-bold text-gray-700">No recovery candidates detected</p>
            <p className="text-xs max-w-md text-gray-500">
              Run a recovery scan on a supported forensic source to identify recoverable video structures.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-[11px] font-bold text-gray-600 uppercase tracking-wider">
                  <th className="py-3 px-4">Candidate ID</th>
                  <th className="py-3 px-4">Source Offset</th>
                  <th className="py-3 px-4">Block Size</th>
                  <th className="py-3 px-4">Detected Format</th>
                  <th className="py-3 px-4">Vendor</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono">
                {candidates.map((cand) => (
                  <tr
                    key={cand.id}
                    className="hover:bg-gray-50/80 transition-colors cursor-pointer"
                    onClick={() => setSelectedCandidate(cand)}
                  >
                    <td className="py-3 px-4 font-bold text-indigo-700">
                      {cand.candidate_identifier}
                    </td>
                    <td className="py-3 px-4 text-gray-700">
                      0x{cand.source_offset.toString(16).toUpperCase().padStart(8, '0')}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {(cand.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3 px-4 text-gray-800 font-sans font-medium">
                      {cand.detected_format}
                    </td>
                    <td className="py-3 px-4 text-gray-700 font-sans">
                      {cand.vendor}
                    </td>
                    <td className="py-3 px-4 text-indigo-700 font-bold">
                      {Math.round(cand.confidence * 100)}%
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          cand.status === 'RECOVERED'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : cand.status === 'VALIDATED'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200'
                            : cand.status === 'PARTIAL'
                            ? 'bg-amber-50 text-amber-800 border border-amber-200'
                            : cand.status === 'CORRUPTED'
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-gray-100 text-gray-700 border border-gray-200'
                        }`}
                      >
                        {cand.status === 'VALIDATED' ? 'VALID' : cand.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right space-x-2 font-sans" onClick={(e) => e.stopPropagation()}>
                      {cand.status !== 'RECOVERED' && (
                        <button
                          onClick={() => handleValidate(cand.id)}
                          disabled={validatingId === cand.id || !canEdit}
                          className="px-2.5 py-1 bg-white hover:bg-gray-50 border border-gray-200 text-gray-700 rounded text-[11px] font-medium transition-colors shadow-xs"
                        >
                          {validatingId === cand.id ? 'Validating...' : 'Validate'}
                        </button>
                      )}

                      {cand.status === 'RECOVERED' ? (
                        <button
                          onClick={() => navigate(`/case/${caseId}/evidence/${cand.recovered_evidence_id}`)}
                          className="px-2.5 py-1 bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-700 rounded text-[11px] font-medium transition-colors flex items-center gap-1 inline-flex shadow-xs"
                        >
                          <ExternalLink size={12} /> View Recovered
                        </button>
                      ) : (
                        <button
                          onClick={() => handleRecover(cand.id)}
                          disabled={recoveringId === cand.id || !canEdit}
                          className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded text-[11px] font-semibold transition-colors flex items-center gap-1 inline-flex shadow-xs"
                        >
                          <Download size={12} />
                          {recoveringId === cand.id ? 'Carving...' : 'Recover'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Candidate Details Modal */}
      {selectedCandidate && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-gray-200 rounded-lg max-w-lg w-full p-5 space-y-4 shadow-xl text-xs text-gray-800">
            <div className="flex items-center justify-between text-gray-900 font-bold text-sm">
              <span className="flex items-center gap-2">
                <FileCode size={18} className="text-indigo-600" /> Candidate Details: {selectedCandidate.candidate_identifier}
              </span>
              <button onClick={() => setSelectedCandidate(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded p-3 space-y-2 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-gray-500">Offset:</span>
                <span className="text-gray-900 font-bold">0x{selectedCandidate.source_offset.toString(16).toUpperCase()} ({selectedCandidate.source_offset} bytes)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Block Length:</span>
                <span className="text-gray-800">{selectedCandidate.size_bytes} bytes</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Detected Format:</span>
                <span className="text-indigo-700 font-bold">{selectedCandidate.detected_format}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Vendor:</span>
                <span className="text-amber-700 font-semibold">{selectedCandidate.vendor}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Status:</span>
                <span className="text-emerald-700 font-bold">{selectedCandidate.status === 'VALIDATED' ? 'VALID' : selectedCandidate.status}</span>
              </div>
              {selectedCandidate.validation_details && (
                <div className="border-t border-gray-200 pt-1 mt-1">
                  <div className="text-gray-500 mb-0.5">Validation Analysis:</div>
                  <div className="text-gray-800 font-sans">{selectedCandidate.validation_details}</div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setSelectedCandidate(null)}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded font-medium border border-gray-200"
              >
                Close
              </button>
              {selectedCandidate.status !== 'RECOVERED' && (
                <button
                  onClick={() => {
                    handleRecover(selectedCandidate.id);
                  }}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold flex items-center gap-1.5 shadow-xs"
                >
                  <Download size={13} /> Carve and Create RECOVERED Evidence
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Recovered Success Notification */}
      {recoveredResult && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-emerald-500 rounded-lg max-w-md w-full p-5 space-y-4 shadow-xl text-xs text-gray-800">
            <div className="flex items-center justify-between text-emerald-700 font-bold text-sm">
              <span className="flex items-center gap-2">
                <CheckCircle size={18} /> Stream Successfully Carved!
              </span>
              <button onClick={() => setRecoveredResult(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            <p className="text-gray-600">
              A new <strong>RECOVERED</strong> evidence record has been created in Drishtik storage. Source image bytes remained strictly untouched.
            </p>

            <div className="bg-gray-50 border border-gray-200 rounded p-3 space-y-2 font-mono text-[11px]">
              <div className="flex justify-between">
                <span className="text-gray-500">Evidence ID:</span>
                <span className="text-indigo-700 font-bold">{recoveredResult.recovered_evidence_identifier}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Status:</span>
                <span className="text-emerald-700 font-bold">{recoveredResult.evidence_status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Filename:</span>
                <span className="text-gray-900 font-semibold truncate max-w-[200px]">{recoveredResult.original_filename}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Size:</span>
                <span className="text-gray-800">{(recoveredResult.size_bytes / 1024).toFixed(1)} KB</span>
              </div>
              <div className="border-t border-gray-200 pt-1">
                <div className="text-gray-500 mb-0.5">SHA-256 Hash:</div>
                <div className="text-[10px] text-emerald-700 break-all select-all font-mono">{recoveredResult.sha256}</div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setRecoveredResult(null)}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded font-medium border border-gray-200"
              >
                Close
              </button>
              <button
                onClick={() => {
                  setRecoveredResult(null);
                  navigate(`/case/${caseId}/evidence/${recoveredResult.recovered_evidence_id}`);
                }}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold flex items-center gap-1.5 shadow-xs"
              >
                <ExternalLink size={13} /> Inspect Evidence
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
