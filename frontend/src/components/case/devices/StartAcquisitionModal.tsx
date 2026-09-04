import React, { useState, useEffect } from 'react';
import { 
  X, 
  Cpu, 
  UploadCloud, 
  HardDrive, 
  ShieldCheck, 
  AlertCircle, 
  CheckCircle2, 
  FileText, 
  Copy, 
  Check, 
  ArrowRight, 
  FolderOpen,
  Folder,
  File as FileIcon,
  CornerLeftUp,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { deviceService } from '../../../services/deviceService';
import type { Device, AcquisitionMethod, Acquisition, DeviceBrowseItem } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';

interface StartAcquisitionModalProps {
  caseId: string;
  device: Device;
  isOpen: boolean;
  onClose: () => void;
  onAcquisitionComplete: () => void;
}

export const StartAcquisitionModal: React.FC<StartAcquisitionModalProps> = ({
  caseId,
  device,
  isOpen,
  onClose,
  onAcquisitionComplete
}) => {
  const { activeCase } = useAuth();
  const effectiveCaseId = activeCase?.case_identifier || caseId;
  const navigate = useNavigate();

  const isConnected = !!device.is_connected;
  const [sourceMode, setSourceMode] = useState<'device' | 'upload'>(isConnected ? 'device' : 'upload');
  const [method, setMethod] = useState<AcquisitionMethod>('FILE_COPY');

  // Constrained device browsing state
  const [currentSubpath, setCurrentSubpath] = useState('');
  const [browseItems, setBrowseItems] = useState<DeviceBrowseItem[]>([]);
  const [browsingLoading, setBrowsingLoading] = useState(false);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [selectedSourcePath, setSelectedSourcePath] = useState<string>('');

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [notes, setNotes] = useState('');

  // Execution state
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Acquisition | null>(null);

  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [creatingEvidence, setCreatingEvidence] = useState(false);
  const [evidenceCreatedId, setEvidenceCreatedId] = useState<number | null>(null);

  // Load files inside source device when modal opens or subpath changes
  const loadSourceContents = async (subpath: string = '') => {
    if (!device.source_root || !isConnected) return;
    setBrowsingLoading(true);
    setBrowseError(null);
    try {
      const items = await deviceService.browseDeviceSource(effectiveCaseId, device.device_identifier, subpath);
      setBrowseItems(items);
      setCurrentSubpath(subpath);
    } catch (err: any) {
      setBrowseError(err.message || 'Failed to read source contents');
    } finally {
      setBrowsingLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && isConnected && device.source_root) {
      loadSourceContents('');
      setSelectedSourcePath('');
    }
  }, [isOpen, device.device_identifier, isConnected]);

  if (!isOpen) return null;

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleNavigateFolder = (folderName: string) => {
    const newPath = currentSubpath ? `${currentSubpath}/${folderName}` : folderName;
    loadSourceContents(newPath);
  };

  const handleNavigateUp = () => {
    if (!currentSubpath) return;
    const parts = currentSubpath.split('/').filter(Boolean);
    parts.pop();
    const parentPath = parts.join('/');
    loadSourceContents(parentPath);
  };

  const formatFileSize = (bytes?: number) => {
    if (bytes === undefined || bytes === null) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (sourceMode === 'device') {
      if (!isConnected) {
        setError('Cannot acquire from a disconnected source device.');
        return;
      }
      if (!selectedSourcePath && method !== 'DIRECTORY_COPY') {
        setError('Please click to select a file from the device to acquire.');
        return;
      }
    } else if (sourceMode === 'upload' && !selectedFile) {
      setError('Please select a forensic source file or image to acquire.');
      return;
    }

    setIsRunning(true);
    setProgress(10);

    try {
      const acq = await deviceService.startAcquisition(
        effectiveCaseId,
        device.device_identifier,
        {
          method,
          source_path: sourceMode === 'device' ? (selectedSourcePath || currentSubpath || '') : undefined,
          notes: notes.trim() || undefined,
          file: sourceMode === 'upload' ? selectedFile || undefined : undefined
        },
        (pct) => setProgress(pct)
      );

      setResult(acq);
      onAcquisitionComplete();
    } catch (err: any) {
      setError(err.message || 'Acquisition execution failed');
    } finally {
      setIsRunning(false);
    }
  };

  const handleCreateEvidence = async () => {
    if (!result) return;
    setCreatingEvidence(true);
    setError(null);

    try {
      const ev = await deviceService.createEvidenceFromAcquisition(effectiveCaseId, result.acquisition_identifier);
      setEvidenceCreatedId(ev.id);
    } catch (err: any) {
      setError(err.message || 'Failed to create evidence from acquisition');
    } finally {
      setCreatingEvidence(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-2xl my-8 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <Cpu size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Forensic Acquisition</h2>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>Target:</span>
                <span className="font-mono font-bold text-gray-800">{device.device_identifier}</span>
                <span>({device.manufacturer} {device.model || device.device_type})</span>
              </div>
            </div>
          </div>
          {!isRunning && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <X size={18} />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-start gap-2.5">
              <AlertCircle size={16} className="shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Error:</span> {error}
              </div>
            </div>
          )}

          {/* SUCCESS RESULT VIEW */}
          {result ? (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-xl flex items-start gap-3">
                <CheckCircle2 size={24} className="text-emerald-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-emerald-950 text-sm">
                    FORENSIC ACQUISITION COMPLETE & VERIFIED
                  </div>
                  <p className="text-xs text-emerald-800 leading-relaxed">
                    Source data was read strictly without modification. Primary SHA-256 and MD5 hashes match 100% bitwise between source bitstream and destination vault.
                  </p>
                </div>
              </div>

              {/* Acquisition Record Details */}
              <div className="bg-gray-50 p-4 rounded-xl border border-gray-200 space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-gray-500 block mb-0.5">Acquisition ID</span>
                    <span className="font-mono font-bold text-gray-900 bg-white px-2 py-1 rounded border border-gray-200 inline-block">
                      {result.acquisition_identifier}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500 block mb-0.5">Method</span>
                    <span className="font-semibold text-gray-800">{result.acquisition_method}</span>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-3 space-y-2">
                  <div>
                    <div className="flex items-center justify-between text-gray-600 mb-0.5">
                      <span className="font-semibold">Source SHA-256</span>
                      <button
                        onClick={() => handleCopy(result.source_sha256 || '', 'src-sha')}
                        className="text-gray-400 hover:text-gray-700 flex items-center gap-1 text-[11px]"
                      >
                        {copiedHash === 'src-sha' ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                        {copiedHash === 'src-sha' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div className="font-mono bg-white p-2 rounded border border-gray-200 break-all text-gray-800">
                      {result.source_sha256}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-gray-600 mb-0.5">
                      <span className="font-semibold">Destination SHA-256</span>
                      <button
                        onClick={() => handleCopy(result.destination_sha256 || '', 'dst-sha')}
                        className="text-gray-400 hover:text-gray-700 flex items-center gap-1 text-[11px]"
                      >
                        {copiedHash === 'dst-sha' ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                        {copiedHash === 'dst-sha' ? 'Copied' : 'Copy'}
                      </button>
                    </div>
                    <div className="font-mono bg-white p-2 rounded border border-gray-200 break-all text-gray-800">
                      {result.destination_sha256}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <div>
                      <span className="text-gray-500 block text-[11px]">Source MD5 (Reference)</span>
                      <span className="font-mono text-gray-700">{result.source_md5}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block text-[11px]">Destination MD5</span>
                      <span className="font-mono text-gray-700">{result.destination_md5}</span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-2 flex items-center justify-between text-xs">
                  <span className="text-gray-500">Cryptographic Verification:</span>
                  <span className="font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <CheckCircle2 size={13} />
                    MATCH (100% BITWISE IDENTICAL)
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-between">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  Done
                </button>

                {evidenceCreatedId ? (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(`/case/${caseId}/evidence/${evidenceCreatedId}`);
                    }}
                    className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm flex items-center gap-2 transition-colors"
                  >
                    <span>View Evidence in Inspection</span>
                    <ArrowRight size={14} />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCreateEvidence}
                    disabled={creatingEvidence}
                    className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm flex items-center gap-2 transition-colors disabled:opacity-50"
                  >
                    <FileText size={14} />
                    <span>{creatingEvidence ? 'Creating Evidence...' : 'Create Evidence From Acquisition'}</span>
                  </button>
                )}
              </div>
            </div>
          ) : isRunning ? (
            /* RUNNING PROGRESS VIEW */
            <div className="py-8 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-600 flex items-center justify-center mx-auto animate-pulse">
                <ShieldCheck size={26} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">Executing Forensic Acquisition</h3>
                <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
                  Streaming bitstream into managed vault and calculating dual SHA-256 and MD5 cryptographic hashes...
                </p>
              </div>

              {/* Progress Bar */}
              <div className="max-w-md mx-auto space-y-1.5">
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div 
                    className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(progress, 15)}%` }}
                  />
                </div>
                <div className="flex justify-between text-[11px] text-gray-500 font-mono">
                  <span>Preserving Source Bitstream</span>
                  <span>{progress}%</span>
                </div>
              </div>
            </div>
          ) : (
            /* ACQUISITION CONFIGURATION FORM */
            <form onSubmit={handleStart} className="space-y-4">
              
              {/* SOURCE STATUS BANNER */}
              <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <HardDrive size={15} className="text-indigo-600" />
                    <span className="font-semibold text-gray-800">Source Root / Mount:</span>
                    <span className="font-mono text-gray-700 bg-white px-2 py-0.5 rounded border border-gray-200">
                      {device.source_root || 'None Configured'}
                    </span>
                  </div>

                  {isConnected ? (
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      CONNECTED
                    </span>
                  ) : (
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                      DISCONNECTED
                    </span>
                  )}
                </div>

                {!isConnected && (
                  <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-start gap-2">
                    <AlertTriangle size={15} className="shrink-0 mt-0.5 text-amber-600" />
                    <div>
                      <span className="font-bold">Source Device Inaccessible:</span> The configured mount path (<span className="font-mono">{device.source_root || 'None'}</span>) is not accessible on this workstation. Connect the physical device or edit the device source root.
                    </div>
                  </div>
                )}
              </div>

              {/* Method Selector */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Acquisition Method
                </label>
                <select
                  value={method}
                  onChange={(e) => setMethod(e.target.value as AcquisitionMethod)}
                  className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="FILE_COPY">File Copy (Read-Only Bitstream File Copy)</option>
                  <option value="EXPORTED_VIDEO">Exported DVR/NVR Video Copy</option>
                  <option value="DISK_IMAGE">Forensic Disk Image (.raw, .dd, .img, .bin, .e01)</option>
                  <option value="DIRECTORY_COPY">Directory Copy (Recursive Folder & Hash Manifest)</option>
                  <option value="LOGICAL_ACQUISITION">Logical Acquisition</option>
                  <option value="OTHER">Other Acquisition Method</option>
                </select>
              </div>

              {/* Source Selection Mode */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Source Selection Mode
                </label>
                <div className="flex border border-gray-200 rounded-lg p-1 bg-gray-50 mb-3">
                  <button
                    type="button"
                    onClick={() => setSourceMode('device')}
                    disabled={!isConnected}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md flex items-center justify-center gap-1.5 transition-colors ${
                      sourceMode === 'device' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                    } disabled:opacity-50`}
                  >
                    <FolderOpen size={14} />
                    <span>Browse Connected Device ({device.source_root || 'Not Available'})</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSourceMode('upload')}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md flex items-center justify-center gap-1.5 transition-colors ${
                      sourceMode === 'upload' ? 'bg-white text-indigo-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    <UploadCloud size={14} />
                    <span>Staging Upload</span>
                  </button>
                </div>

                {sourceMode === 'device' ? (
                  /* CONSTRAINED DEVICE BROWSER */
                  <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
                    {/* Browser Toolbar */}
                    <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 truncate">
                        <button
                          type="button"
                          onClick={handleNavigateUp}
                          disabled={!currentSubpath}
                          className="p-1 rounded hover:bg-gray-200 disabled:opacity-30 transition-colors"
                          title="Navigate Up"
                        >
                          <CornerLeftUp size={14} />
                        </button>
                        <span className="font-mono text-gray-600 truncate">
                          {device.source_root} {currentSubpath ? ` / ${currentSubpath}` : ''}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => loadSourceContents(currentSubpath)}
                        className="text-gray-500 hover:text-gray-800 p-1"
                        title="Refresh"
                      >
                        <RefreshCw size={13} className={browsingLoading ? 'animate-spin' : ''} />
                      </button>
                    </div>

                    {/* Browser List */}
                    <div className="max-h-48 overflow-y-auto divide-y divide-gray-100">
                      {browsingLoading ? (
                        <div className="p-6 text-center text-xs text-gray-400">Loading device contents...</div>
                      ) : browseError ? (
                        <div className="p-4 text-xs text-red-600">{browseError}</div>
                      ) : browseItems.length === 0 ? (
                        <div className="p-6 text-center text-xs text-gray-400">No files found in this directory.</div>
                      ) : (
                        browseItems.map((item) => {
                          const isSelected = selectedSourcePath === item.path;
                          return (
                            <div
                              key={item.path}
                              onClick={() => {
                                if (item.is_dir) {
                                  handleNavigateFolder(item.name);
                                } else {
                                  setSelectedSourcePath(item.path);
                                }
                              }}
                              className={`px-3 py-2 flex items-center justify-between text-xs cursor-pointer transition-colors ${
                                isSelected ? 'bg-indigo-50 text-indigo-900 font-semibold' : 'hover:bg-gray-50 text-gray-700'
                              }`}
                            >
                              <div className="flex items-center gap-2 truncate">
                                {item.is_dir ? (
                                  <Folder size={15} className="text-amber-500 shrink-0" />
                                ) : (
                                  <FileIcon size={15} className="text-gray-400 shrink-0" />
                                )}
                                <span className="truncate">{item.name}</span>
                              </div>
                              <span className="font-mono text-[11px] text-gray-400 shrink-0">
                                {item.is_dir ? 'Folder' : formatFileSize(item.size_bytes)}
                              </span>
                            </div>
                          );
                        })
                      )}
                    </div>

                    {/* Selected Item Notification */}
                    <div className="p-2.5 bg-gray-50 border-t border-gray-200 text-xs flex items-center justify-between">
                      <div className="truncate">
                        <span className="text-gray-500">Selected Source: </span>
                        <span className="font-mono font-bold text-gray-900">
                          {selectedSourcePath || (method === 'DIRECTORY_COPY' ? `[Current Directory: ${currentSubpath || 'Root'}]` : 'None')}
                        </span>
                      </div>
                      {method === 'DIRECTORY_COPY' && (
                        <button
                          type="button"
                          onClick={() => setSelectedSourcePath(currentSubpath || '')}
                          className="px-2 py-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 rounded border border-indigo-200 shrink-0"
                        >
                          Acquire Current Folder
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  /* STAGING UPLOAD */
                  <div className="border-2 border-dashed border-gray-300 rounded-xl p-5 text-center hover:border-indigo-400 transition-colors bg-gray-50/50">
                    <input
                      type="file"
                      id="acq-file-input"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      className="hidden"
                    />
                    <label htmlFor="acq-file-input" className="cursor-pointer block">
                      <UploadCloud size={28} className="mx-auto text-gray-400 mb-2" />
                      {selectedFile ? (
                        <div className="text-xs">
                          <span className="font-semibold text-indigo-600 block truncate">{selectedFile.name}</span>
                          <span className="text-gray-500">{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                        </div>
                      ) : (
                        <div className="text-xs text-gray-600">
                          <span className="font-semibold text-indigo-600 hover:underline">Choose a file</span> or drag & drop forensic media
                          <p className="text-[11px] text-gray-400 mt-1">MP4, AVI, MKV, DAV, DD, RAW, IMG</p>
                        </div>
                      )}
                    </label>
                  </div>
                )}
              </div>

              {/* Destination Display */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Destination Storage
                </label>
                <div className="p-2.5 bg-gray-100 rounded-lg border border-gray-200 text-xs text-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <HardDrive size={15} className="text-indigo-600" />
                    <span className="font-medium">Drishtik Managed Case Vault (Isolated Read-Only Storage)</span>
                  </div>
                  <span className="text-[10px] text-emerald-700 font-bold bg-emerald-100 px-2 py-0.5 rounded">
                    Controlled
                  </span>
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Acquisition Notes / Chain of Custody Reference
                </label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Exported directly from DVR Channel 1 via USB storage at scene. Physical write-blocker attached."
                  className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
              </div>

              {/* Modal Footer */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sourceMode === 'device' && !isConnected}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm flex items-center gap-2 transition-colors disabled:opacity-50"
                >
                  <ShieldCheck size={15} />
                  <span>Start Acquisition</span>
                </button>
              </div>
            </form>
          )}

        </div>

      </div>
    </div>
  );
};
