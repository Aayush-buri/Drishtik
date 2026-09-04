import React, { useState } from 'react';
import { X, Edit3, AlertCircle } from 'lucide-react';
import { deviceService } from '../../../services/deviceService';
import type { Device, DeviceType, DeviceStatus } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';

interface EditDeviceModalProps {
  caseId: string;
  device: Device;
  isOpen: boolean;
  onClose: () => void;
  onDeviceUpdated: () => void;
}

export const EditDeviceModal: React.FC<EditDeviceModalProps> = ({
  caseId,
  device,
  isOpen,
  onClose,
  onDeviceUpdated
}) => {
  const { activeCase } = useAuth();
  const effectiveCaseId = activeCase?.case_identifier || caseId;

  const [deviceType, setDeviceType] = useState<DeviceType>(device.device_type);
  const [manufacturer, setManufacturer] = useState(device.manufacturer || 'Unknown');
  const [model, setModel] = useState(device.model || '');
  const [serialNumber, setSerialNumber] = useState(device.serial_number || '');
  const [firmwareVersion, setFirmwareVersion] = useState(device.firmware_version || '');
  const [ipAddress, setIpAddress] = useState(device.ip_address || '');
  const [macAddress, setMacAddress] = useState(device.mac_address || '');
  const [storageCapacity, setStorageCapacity] = useState(device.storage_capacity || '');
  const [channelCount, setChannelCount] = useState<string>(device.channel_count?.toString() || '');
  const [location, setLocation] = useState(device.location || '');
  const [sourceRoot, setSourceRoot] = useState(device.source_root || '');
  const [notes, setNotes] = useState(device.notes || '');
  const [status, setStatus] = useState<DeviceStatus>(device.status);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await deviceService.updateDevice(effectiveCaseId, device.device_identifier, {
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
        notes: notes.trim() || undefined,
        status: status
      });

      onDeviceUpdated();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update device');
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
              <Edit3 size={18} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-gray-900">Edit Device Information</h2>
              <span className="font-mono text-xs text-indigo-600 font-bold">{device.device_identifier}</span>
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
                Device Type
              </label>
              <select
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value as DeviceType)}
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="DVR">DVR (Digital Video Recorder)</option>
                <option value="NVR">NVR (Network Video Recorder)</option>
                <option value="INTERNAL_HDD">Internal HDD / Storage Drive</option>
                <option value="EXTERNAL_STORAGE">External Storage / SD / USB</option>
                <option value="DISK_IMAGE">Forensic Disk Image (.dd, .raw, .img)</option>
                <option value="OTHER">Other Hardware Source</option>
              </select>
            </div>

            {/* Status */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Device Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as DeviceStatus)}
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ACTIVE">ACTIVE</option>
                <option value="INACTIVE">INACTIVE</option>
                <option value="ACQUIRED">ACQUIRED</option>
                <option value="ARCHIVED">ARCHIVED</option>
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
                className="w-full text-xs px-3 py-2 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Location */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Physical Location
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
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
                Forensic containment: acquisitions are strictly bounded to this drive letter or mount path.
              </p>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Investigator Notes
            </label>
            <textarea
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
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
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
};
