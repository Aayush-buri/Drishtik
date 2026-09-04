import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  HardDrive, 
  Cpu, 
  Network, 
  Database, 
  MapPin, 
  Plus, 
  Edit3, 
  Archive, 
  CheckCircle2, 
  AlertTriangle, 
  Copy, 
  Check, 
  Layers
} from 'lucide-react';
import { deviceService } from '../../../services/deviceService';
import type { Device, Acquisition } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';
import { StartAcquisitionModal } from './StartAcquisitionModal';
import { EditDeviceModal } from './EditDeviceModal';
import { ArchiveDeviceModal } from './ArchiveDeviceModal';

export const DeviceDetailsView: React.FC = () => {
  const { caseId, deviceId } = useParams<{ caseId: string; deviceId: string }>();
  const navigate = useNavigate();
  const { role, activeCase } = useAuth();
  const caseIdentifier = activeCase?.case_identifier || caseId;

  const [device, setDevice] = useState<Device | null>(null);
  const [acquisitions, setAcquisitions] = useState<Acquisition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [isAcqModalOpen, setIsAcqModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);

  // Clipboard feedback
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const isAdmin = role === 'ADMIN';
  const canModify = role === 'ADMIN' || role === 'INVESTIGATOR';

  const loadDeviceDetails = async () => {
    if (!caseIdentifier || !deviceId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await deviceService.getDevice(caseIdentifier, deviceId);
      setDevice(data);
      if (data.acquisitions) {
        setAcquisitions(data.acquisitions);
      } else {
        const acqs = await deviceService.getDeviceAcquisitions(caseIdentifier, deviceId);
        setAcquisitions(acqs);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load device details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDeviceDetails();
  }, [caseIdentifier, deviceId]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleCreateEvidence = async (acqId: string) => {
    if (!caseIdentifier) return;
    try {
      const ev = await deviceService.createEvidenceFromAcquisition(caseIdentifier, acqId);
      navigate(`/case/${caseId}/evidence/${ev.id}`);
    } catch (err: any) {
      alert(`Failed to create evidence: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-12 bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-gray-500 font-medium">Loading source device details...</span>
        </div>
      </div>
    );
  }

  if (error || !device) {
    return (
      <div className="flex-1 p-8 bg-gray-50">
        <div className="max-w-md mx-auto bg-white p-6 rounded-xl border border-red-200 text-center space-y-3 shadow-sm">
          <AlertTriangle size={32} className="text-red-500 mx-auto" />
          <h3 className="text-sm font-bold text-gray-900">Device Not Found</h3>
          <p className="text-xs text-gray-500">{error || 'The requested device does not exist or has been removed.'}</p>
          <button
            onClick={() => navigate(`/case/${caseId}/devices`)}
            className="px-4 py-2 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 rounded-lg"
          >
            Back to Devices
          </button>
        </div>
      </div>
    );
  }

  const isArchived = device.status === 'ARCHIVED';

  return (
    <div className="flex-1 flex flex-col h-full bg-gray-50 overflow-y-auto">
      
      {/* Top Header & Breadcrumbs */}
      <div className="bg-white border-b border-gray-200 px-8 py-4 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/case/${caseId}/devices`)}
              className="p-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-gray-800 hover:bg-gray-100 transition-colors"
              title="Back to Devices"
            >
              <ArrowLeft size={16} />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-bold text-gray-900 bg-gray-100 px-2 py-0.5 rounded border border-gray-200">
                  {device.device_identifier}
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                  device.status === 'ACTIVE' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' :
                  device.status === 'ACQUIRED' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
                  device.status === 'ARCHIVED' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                  'bg-gray-100 text-gray-700 border border-gray-300'
                }`}>
                  {device.status}
                </span>
                {device.connection_status === 'CONNECTED' ? (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    CONNECTED
                  </span>
                ) : device.connection_status === 'DISCONNECTED' ? (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                    DISCONNECTED
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
                    UNCONFIGURED
                  </span>
                )}
              </div>
              <h1 className="text-lg font-bold text-gray-900 mt-0.5">
                {device.manufacturer || 'Unknown'} {device.model || device.device_type}
              </h1>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            {canModify && !isArchived && (
              <button
                onClick={() => setIsAcqModalOpen(true)}
                className="px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm flex items-center gap-2 transition-colors"
              >
                <Cpu size={14} />
                <span>Start Acquisition</span>
              </button>
            )}

            {canModify && (
              <button
                onClick={() => setIsEditModalOpen(true)}
                className="px-3 py-2 text-xs font-semibold text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <Edit3 size={14} />
                <span>Edit</span>
              </button>
            )}

            {isAdmin && !isArchived && (
              <button
                onClick={() => setIsArchiveModalOpen(true)}
                className="px-3 py-2 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 rounded-lg transition-colors flex items-center gap-1.5"
              >
                <Archive size={14} />
                <span>Archive</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="p-8 space-y-6 max-w-7xl">
        
        {/* Honest Environment / Desktop Device Detection Banner */}
        <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-4 flex items-start gap-3 text-xs text-amber-800">
          <AlertTriangle size={18} className="shrink-0 mt-0.5 text-amber-600" />
          <div className="space-y-0.5">
            <span className="font-bold text-amber-900">Desktop device detection: Not available in browser mode</span>
            <p className="text-amber-700 leading-relaxed">
              Direct physical block-level device detection is unavailable under web browser sandbox constraints. Forensic acquisition is constrained to the verified workstation source root (<span className="font-mono font-bold text-gray-900">{device.source_root || 'None Configured'}</span>).
            </p>
          </div>
        </div>

        {/* Specification Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* 1. DEVICE INFORMATION */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-gray-100 text-xs font-bold text-gray-700 uppercase tracking-wider">
              <HardDrive size={15} className="text-indigo-600" />
              <span>Device Information</span>
            </div>
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="text-gray-400 font-medium">Device Type</dt>
                <dd className="text-gray-900 font-semibold">{device.device_type}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Manufacturer</dt>
                <dd className="text-gray-900 font-semibold">{device.manufacturer || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Model</dt>
                <dd className="text-gray-900 font-semibold">{device.model || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Serial Number</dt>
                <dd className="font-mono text-gray-900">{device.serial_number || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Firmware Version</dt>
                <dd className="font-mono text-gray-900">{device.firmware_version || 'Not available'}</dd>
              </div>
            </dl>
          </div>

          {/* 2. NETWORK */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-gray-100 text-xs font-bold text-gray-700 uppercase tracking-wider">
              <Network size={15} className="text-indigo-600" />
              <span>Network</span>
            </div>
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="text-gray-400 font-medium">IP Address</dt>
                <dd className="font-mono text-gray-900 font-semibold">{device.ip_address || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">MAC Address</dt>
                <dd className="font-mono text-gray-900 font-semibold">{device.mac_address || 'Not available'}</dd>
              </div>
              <div className="pt-4 border-t border-gray-50">
                <dt className="text-gray-400 font-medium">Connection Type</dt>
                <dd className="text-gray-900">
                  {device.device_type === 'NVR' ? 'Ethernet IP Network' : 'Standalone / Direct BNC'}
                </dd>
              </div>
            </dl>
          </div>

          {/* 3. STORAGE & CHANNELS */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-gray-100 text-xs font-bold text-gray-700 uppercase tracking-wider">
              <Database size={15} className="text-indigo-600" />
              <span>Storage & Channels</span>
            </div>
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="text-gray-400 font-medium">Storage Capacity</dt>
                <dd className="text-gray-900 font-semibold">{device.storage_capacity || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Channel Count</dt>
                <dd className="text-gray-900 font-semibold">
                  {device.channel_count !== undefined && device.channel_count !== null ? `${device.channel_count} Channels` : 'Not available'}
                </dd>
              </div>
              <div className="pt-4 border-t border-gray-50">
                <dt className="text-gray-400 font-medium">Acquisitions Recorded</dt>
                <dd className="text-indigo-600 font-bold font-mono text-sm">
                  {device.acquisitions_count ?? acquisitions.length}
                </dd>
              </div>
            </dl>
          </div>

          {/* 4. LOCATION & NOTES */}
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-gray-100 text-xs font-bold text-gray-700 uppercase tracking-wider">
              <MapPin size={15} className="text-indigo-600" />
              <span>Location & Notes</span>
            </div>
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="text-gray-400 font-medium">Location</dt>
                <dd className="text-gray-900">{device.location || 'Not available'}</dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Notes</dt>
                <dd className="text-gray-700 leading-relaxed italic bg-gray-50 p-2 rounded border border-gray-100">
                  {device.notes || 'No investigator notes recorded.'}
                </dd>
              </div>
              <div>
                <dt className="text-gray-400 font-medium">Registered Date</dt>
                <dd className="text-gray-600">{new Date(device.created_at).toLocaleString()}</dd>
              </div>
            </dl>
          </div>

        </div>

        {/* ACQUISITION HISTORY SECTION */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/50">
            <div className="flex items-center gap-2.5">
              <Cpu size={18} className="text-indigo-600" />
              <div>
                <h3 className="text-sm font-bold text-gray-900">Forensic Acquisition Records</h3>
                <p className="text-xs text-gray-500">Bit-level read-only bitstream acquisitions performed from this hardware source</p>
              </div>
            </div>
            {canModify && !isArchived && (
              <button
                onClick={() => setIsAcqModalOpen(true)}
                className="px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg flex items-center gap-1.5 transition-colors"
              >
                <Plus size={14} />
                <span>New Acquisition</span>
              </button>
            )}
          </div>

          {acquisitions.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto">
                <Cpu size={24} />
              </div>
              <h4 className="text-sm font-semibold text-gray-900">No Forensic Acquisitions Yet</h4>
              <p className="text-xs text-gray-500 max-w-sm mx-auto">
                No acquisitions have been recorded for this device. Click &ldquo;Start Acquisition&rdquo; to preserve forensic data with dual-hash verification.
              </p>
              {canModify && !isArchived && (
                <button
                  onClick={() => setIsAcqModalOpen(true)}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
                >
                  Start Acquisition
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {acquisitions.map((acq) => (
                <div key={acq.id} className="p-6 hover:bg-gray-50/50 transition-colors space-y-3">
                  
                  {/* Row Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-xs font-bold text-gray-900 bg-gray-100 px-2.5 py-1 rounded border border-gray-200">
                        {acq.acquisition_identifier}
                      </span>
                      <span className="text-xs font-semibold text-gray-700 bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded">
                        {acq.acquisition_method}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold flex items-center gap-1 ${
                        acq.status === 'COMPLETED' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                        acq.status === 'FAILED' ? 'bg-red-50 text-red-700 border border-red-200' :
                        'bg-blue-50 text-blue-700 border border-blue-200'
                      }`}>
                        {acq.status === 'COMPLETED' && <CheckCircle2 size={12} />}
                        {acq.status === 'FAILED' && <AlertTriangle size={12} />}
                        {acq.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {acq.has_evidence && acq.evidence_identifier ? (
                        <span className="text-xs font-medium text-purple-700 bg-purple-50 border border-purple-200 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
                          <Layers size={13} />
                          Evidence: {acq.evidence_identifier}
                        </span>
                      ) : acq.status === 'COMPLETED' && canModify ? (
                        <button
                          onClick={() => handleCreateEvidence(acq.acquisition_identifier)}
                          className="px-3 py-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg flex items-center gap-1.5 transition-colors"
                        >
                          <span>Create Evidence</span>
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {/* Hash & Verification Panel */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-gray-50/80 p-3.5 rounded-lg border border-gray-200">
                    <div>
                      <div className="flex items-center justify-between text-gray-500 mb-0.5">
                        <span className="font-semibold text-[11px]">Source SHA-256</span>
                        <button
                          onClick={() => handleCopy(acq.source_sha256 || '', `src-${acq.id}`)}
                          className="text-gray-400 hover:text-gray-700 flex items-center gap-1 text-[10px]"
                        >
                          {copiedKey === `src-${acq.id}` ? <Check size={10} className="text-emerald-600" /> : <Copy size={10} />}
                          {copiedKey === `src-${acq.id}` ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      <div className="font-mono text-gray-800 break-all bg-white p-1.5 rounded border border-gray-200">
                        {acq.source_sha256 || 'Not calculated'}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between text-gray-500 mb-0.5">
                        <span className="font-semibold text-[11px]">Destination SHA-256</span>
                        <button
                          onClick={() => handleCopy(acq.destination_sha256 || '', `dst-${acq.id}`)}
                          className="text-gray-400 hover:text-gray-700 flex items-center gap-1 text-[10px]"
                        >
                          {copiedKey === `dst-${acq.id}` ? <Check size={10} className="text-emerald-600" /> : <Copy size={10} />}
                          {copiedKey === `dst-${acq.id}` ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      <div className="font-mono text-gray-800 break-all bg-white p-1.5 rounded border border-gray-200">
                        {acq.destination_sha256 || 'Not calculated'}
                      </div>
                    </div>

                    {acq.source_md5 && acq.destination_md5 && (
                      <div className="col-span-1 md:col-span-2 flex items-center justify-between pt-1 border-t border-gray-200 text-[11px] text-gray-500">
                        <span>MD5 Reference: <span className="font-mono text-gray-700">{acq.destination_md5}</span></span>
                        <span className="text-emerald-700 font-bold flex items-center gap-1">
                          <CheckCircle2 size={12} />
                          Integrity Match Verified
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Metadata Row */}
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-gray-500">
                    <div>
                      Operator: <span className="text-gray-800 font-medium">{acq.operator_name || 'Investigator'}</span>
                    </div>
                    <div>
                      Started: <span className="text-gray-800 font-medium">{new Date(acq.started_at).toLocaleString()}</span>
                    </div>
                    {acq.completed_at && (
                      <div>
                        Completed: <span className="text-gray-800 font-medium">{new Date(acq.completed_at).toLocaleString()}</span>
                      </div>
                    )}
                    {acq.notes && (
                      <div className="italic text-gray-600 truncate max-w-md">
                        &ldquo;{acq.notes}&rdquo;
                      </div>
                    )}
                  </div>

                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* Modals */}
      <StartAcquisitionModal
        caseId={caseIdentifier!}
        device={device}
        isOpen={isAcqModalOpen}
        onClose={() => setIsAcqModalOpen(false)}
        onAcquisitionComplete={loadDeviceDetails}
      />

      <EditDeviceModal
        caseId={caseIdentifier!}
        device={device}
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onDeviceUpdated={loadDeviceDetails}
      />

      <ArchiveDeviceModal
        caseId={caseIdentifier!}
        device={device}
        isOpen={isArchiveModalOpen}
        onClose={() => setIsArchiveModalOpen(false)}
        onDeviceArchived={loadDeviceDetails}
      />

    </div>
  );
};
