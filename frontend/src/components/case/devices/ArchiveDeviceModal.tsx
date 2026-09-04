import React, { useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { deviceService } from '../../../services/deviceService';
import type { Device } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';

interface ArchiveDeviceModalProps {
  caseId: string;
  device: Device;
  isOpen: boolean;
  onClose: () => void;
  onDeviceArchived: () => void;
}

export const ArchiveDeviceModal: React.FC<ArchiveDeviceModalProps> = ({
  caseId,
  device,
  isOpen,
  onClose,
  onDeviceArchived
}) => {
  const { activeCase } = useAuth();
  const effectiveCaseId = activeCase?.case_identifier || caseId;

  const [confirmed, setConfirmed] = useState(false);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const hasAcquisitions = (device.acquisitions_count ?? 0) > 0;

  const handleArchive = async () => {
    setLoading(true);
    setError(null);

    try {
      await deviceService.archiveDevice(effectiveCaseId, device.device_identifier, confirmed, reason);
      onDeviceArchived();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to archive device');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-amber-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-100 border border-amber-200 flex items-center justify-center text-amber-700">
              <AlertTriangle size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Archive Device</h2>
              <span className="font-mono text-xs font-bold text-gray-600">{device.device_identifier}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              {error}
            </div>
          )}

          <p className="text-xs text-gray-600 leading-relaxed">
            Archiving marks this device as inactive in the active inventory while preserving all historic acquisitions, evidence links, and cryptographic audit records.
          </p>

          {hasAcquisitions ? (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-2">
              <div className="font-bold flex items-center gap-1.5">
                <AlertTriangle size={14} className="text-amber-600" />
                Active Acquisitions Warning
              </div>
              <p>
                This device has <strong>{device.acquisitions_count}</strong> associated forensic acquisition(s). All acquisition records and derived evidence will remain accessible in case history.
              </p>
              <label className="flex items-center gap-2 pt-1 font-medium cursor-pointer">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="rounded border-amber-300 text-amber-600 focus:ring-amber-500"
                />
                <span>I confirm archiving this device and its {device.acquisitions_count} acquisition(s).</span>
              </label>
            </div>
          ) : (
            <p className="text-xs text-gray-500 italic">
              This device has no recorded acquisitions.
            </p>
          )}

          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Reason for Archiving (Optional)
            </label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Returned to owner / Evidence custody transferred"
              className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-gray-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleArchive}
              disabled={loading || (hasAcquisitions && !confirmed)}
              className="px-4 py-2 text-xs font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {loading ? 'Archiving...' : 'Confirm Archive'}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
