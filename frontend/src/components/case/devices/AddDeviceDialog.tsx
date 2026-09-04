import React, { useState } from 'react';
import { X, HardDrive, AlertCircle } from 'lucide-react';
import { deviceService } from '../../../services/deviceService';
import type { DeviceType } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';

interface AddDeviceDialogProps {
  caseId: string;
  isOpen: boolean;
  onClose: () => void;
  onDeviceCreated: () => void;
}

export const AddDeviceDialog: React.FC<AddDeviceDialogProps> = ({
  caseId,
  isOpen,
  onClose,
  onDeviceCreated
}) => {
  const { activeCase } = useAuth();
  const effectiveCaseId = activeCase?.case_identifier || caseId;

  const [deviceType, setDeviceType] = useState<DeviceType>('DVR');
  const [manufacturer, setManufacturer] = useState('Unknown');
  const [model, setModel] = useState('');
  const [serialNumber, setSerialNumber] = useState('');
  const [firmwareVersion, setFirmwareVersion] = useState('');
  const [ipAddress, setIpAddress] = useState('');
  const [macAddress, setMacAddress] = useState('');
  const [storageCapacity, setStorageCapacity] = useState('');
  const [channelCount, setChannelCount] = useState<string>('');
  const [location, setLocation] = useState('');
  const [sourceRoot, setSourceRoot] = useState('');
  const [notes, setNotes] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await deviceService.createDevice(effectiveCaseId, {
        device_type: deviceType,
        manufacturer: manufacturer.trim() || 'Unknown',
        model: model.trim() || undefined,
        serial_number: serialNumber.trim() || undefined,
        firmware_version: firmwareVersion.trim() || undefined,
        ip_address: ipAddress.trim() || undefined,
        mac_address: macAddress.trim() || undefined,
        storage_capacity: storageCapacity.trim() || undefined,
        channel_count: channelCount ? parseInt(channelCount, 10) : undefined,
        location: location.trim() || undefined,
        source_root: sourceRoot.trim() || undefined,
        notes: notes.trim() || undefined
      });

      onDeviceCreated();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create device');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-2xl my-8 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
              <HardDrive size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Register Source Device</h2>
              <p className="text-xs text-gray-500">Document CCTV hardware source before acquisition</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Device Type */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Device Type <span className="text-red-500">*</span>
              </label>
              <select
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value as DeviceType)}
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                required
              >
                <option value="DVR">DVR (Digital Video Recorder)</option>
                <option value="NVR">NVR (Network Video Recorder)</option>
                <option value="INTERNAL_HDD">Internal HDD / Storage Drive</option>
                <option value="EXTERNAL_STORAGE">External Storage / SD / USB</option>
                <option value="DISK_IMAGE">Forensic Disk Image (.dd, .raw, .img)</option>
                <option value="OTHER">Other Hardware Source</option>
              </select>
            </div>

            {/* Manufacturer */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Manufacturer
              </label>
              <input
                type="text"
                value={manufacturer}
                onChange={(e) => setManufacturer(e.target.value)}
                placeholder="e.g. CP Plus, Hikvision, Dahua, Unknown"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Model */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Model Number
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="e.g. CP-UVR-0801E1-V3"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Serial Number */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Serial Number
              </label>
              <input
                type="text"
                value={serialNumber}
                onChange={(e) => setSerialNumber(e.target.value)}
                placeholder="e.g. SN-8928472910"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Firmware Version */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Firmware Version
              </label>
              <input
                type="text"
                value={firmwareVersion}
                onChange={(e) => setFirmwareVersion(e.target.value)}
                placeholder="e.g. V3.2.1-build2023"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Channel Count */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Channel Count
              </label>
              <input
                type="number"
                value={channelCount}
                onChange={(e) => setChannelCount(e.target.value)}
                placeholder="e.g. 4, 8, 16, 32"
                min="1"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Storage Capacity */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Storage Capacity
              </label>
              <input
                type="text"
                value={storageCapacity}
                onChange={(e) => setStorageCapacity(e.target.value)}
                placeholder="e.g. 1 TB, 2 TB, 500 GB"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Physical Location */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Physical Location / Seizure Site
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Ground Floor Server Room, Rack 2"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* IP Address */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                IP Address
              </label>
              <input
                type="text"
                value={ipAddress}
                onChange={(e) => setIpAddress(e.target.value)}
                placeholder="e.g. 192.168.1.108"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* MAC Address */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                MAC Address
              </label>
              <input
                type="text"
                value={macAddress}
                onChange={(e) => setMacAddress(e.target.value)}
                placeholder="e.g. 00:1A:2B:3C:4D:5E"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Source Root / Workstation Mount Path */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Source Root / Workstation Mount Path
              </label>
              <input
                type="text"
                value={sourceRoot}
                onChange={(e) => setSourceRoot(e.target.value)}
                placeholder="e.g. E:\ (for USB/SD drive) or C:\evidence_sources\dvr_disk"
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
              />
              <p className="text-[11px] text-gray-500 mt-1">
                Forensic containment: acquisitions will be strictly bounded to this drive letter or mount point.
              </p>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Investigator Notes / Physical Condition
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Recovered with original power adapter and single 1TB Seagate Barracuda drive. Tamper seals intact."
              className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>

          {/* Footer Actions */}
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
              disabled={loading}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
            >
              {loading ? 'Registering...' : 'Register Device'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
