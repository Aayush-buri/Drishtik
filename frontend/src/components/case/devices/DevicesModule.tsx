import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  HardDrive, 
  Server, 
  Disc, 
  Cpu, 
  Search, 
  Filter, 
  Plus, 
  ArrowRight,
  MapPin,
  AlertCircle
} from 'lucide-react';
import { deviceService } from '../../../services/deviceService';
import type { Device, DeviceType } from '../../../services/deviceService';
import { useAuth } from '../../../hooks/useAuth';
import { AddDeviceDialog } from './AddDeviceDialog';

export const DevicesModule: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { role, activeCase } = useAuth();
  const caseIdentifier = activeCase?.case_identifier || caseId;

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [typeFilter, setTypeFilter] = useState<string>('ALL');

  // Modal
  const [isAddOpen, setIsAddOpen] = useState(false);

  const canCreate = role === 'ADMIN' || role === 'INVESTIGATOR';

  const loadDevices = async () => {
    if (!caseIdentifier) return;
    try {
      setLoading(true);
      setError(null);
      const data = await deviceService.getDevices(caseIdentifier, {
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        device_type: typeFilter !== 'ALL' ? typeFilter : undefined,
        search: search.trim() || undefined
      });
      setDevices(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load devices');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDevices();
  }, [caseIdentifier, statusFilter, typeFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      loadDevices();
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  const getDeviceIcon = (type: DeviceType) => {
    switch (type) {
      case 'DVR':
      case 'NVR':
        return <Server size={20} className="text-indigo-600" />;
      case 'INTERNAL_HDD':
      case 'EXTERNAL_STORAGE':
        return <HardDrive size={20} className="text-indigo-600" />;
      case 'DISK_IMAGE':
        return <Disc size={20} className="text-indigo-600" />;
      default:
        return <Cpu size={20} className="text-indigo-600" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-gray-50 overflow-y-auto">
      
      {/* Header Bar */}
      <div className="bg-white border-b border-gray-200 px-8 py-5 shrink-0">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Source Devices</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Documented CCTV hardware, DVR/NVR recorders, and forensic storage images
            </p>
          </div>

          {canCreate && (
            <button
              onClick={() => setIsAddOpen(true)}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm flex items-center gap-2 transition-colors self-start sm:self-auto"
            >
              <Plus size={15} />
              <span>Add Device</span>
            </button>
          )}
        </div>

        {/* Search & Filter Controls */}
        <div className="mt-4 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          
          {/* Search Input */}
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by ID, manufacturer, model, serial, location..."
              className="w-full text-xs pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
            />
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter size={15} className="text-gray-400 shrink-0" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-gray-700"
            >
              <option value="ALL">All Types</option>
              <option value="DVR">DVR</option>
              <option value="NVR">NVR</option>
              <option value="INTERNAL_HDD">Internal HDD</option>
              <option value="EXTERNAL_STORAGE">External Storage</option>
              <option value="DISK_IMAGE">Forensic Disk Image</option>
              <option value="OTHER">Other</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-gray-700 w-full sm:w-auto"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="ACQUIRED">ACQUIRED</option>
              <option value="INACTIVE">INACTIVE</option>
              <option value="ARCHIVED">ARCHIVED</option>
            </select>
          </div>

        </div>
      </div>

      {/* Main Grid Content */}
      <div className="p-8">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-gray-500 font-medium">Loading source devices...</span>
            </div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        ) : devices.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center max-w-lg mx-auto space-y-4 shadow-sm">
            <div className="w-12 h-12 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
              <HardDrive size={24} />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-gray-900">No Source Devices Found</h3>
              <p className="text-xs text-gray-500">
                {search || typeFilter !== 'ALL' || statusFilter !== 'ALL'
                  ? 'No devices match the specified search or filter criteria.'
                  : 'No hardware devices have been registered for this case yet.'}
              </p>
            </div>
            {canCreate && (
              <button
                onClick={() => setIsAddOpen(true)}
                className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
              >
                Register First Device
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {devices.map((device) => (
              <div
                key={device.id}
                onClick={() => navigate(`/case/${caseId}/devices/${device.device_identifier}`)}
                className="bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer p-5 flex flex-col justify-between group space-y-4"
              >
                {/* Top Row: Type, ID & Status */}
                <div>
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-9 h-9 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                        {getDeviceIcon(device.device_type)}
                      </div>
                      <div>
                        <div className="font-mono text-xs font-bold text-gray-900 group-hover:text-indigo-600 transition-colors">
                          {device.device_identifier}
                        </div>
                        <span className="text-[10px] text-gray-500 font-semibold tracking-wider uppercase">
                          {device.device_type}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        device.status === 'ACTIVE' ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' :
                        device.status === 'ACQUIRED' ? 'bg-blue-50 text-blue-700 border border-blue-200' :
                        device.status === 'ARCHIVED' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                        'bg-gray-100 text-gray-700 border border-gray-300'
                      }`}>
                        {device.status}
                      </span>
                      {device.connection_status === 'CONNECTED' ? (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          CONNECTED
                        </span>
                      ) : device.connection_status === 'DISCONNECTED' ? (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          DISCONNECTED
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
                          UNCONFIGURED
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Device Title / Hardware Identity */}
                  <h3 className="text-sm font-bold text-gray-900 group-hover:text-indigo-600 transition-colors">
                    {device.manufacturer || 'Unknown'} {device.model || ''}
                  </h3>
                  {device.serial_number && (
                    <div className="font-mono text-[11px] text-gray-400 mt-0.5">
                      S/N: {device.serial_number}
                    </div>
                  )}
                  {device.source_root && (
                    <div className="font-mono text-[11px] text-gray-600 mt-1 bg-gray-50 px-2 py-0.5 rounded border border-gray-200 inline-block truncate max-w-full">
                      Mount: {device.source_root}
                    </div>
                  )}

                  {/* Technical Specifications */}
                  <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-gray-100 text-xs">
                    <div>
                      <span className="text-gray-400 block text-[10px]">Channels</span>
                      <span className="font-medium text-gray-800">
                        {device.channel_count ? `${device.channel_count} CH` : 'N/A'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-400 block text-[10px]">Storage</span>
                      <span className="font-medium text-gray-800">
                        {device.storage_capacity || 'N/A'}
                      </span>
                    </div>
                  </div>

                  {device.location && (
                    <div className="mt-2.5 text-xs text-gray-500 flex items-center gap-1.5 truncate">
                      <MapPin size={12} className="shrink-0 text-gray-400" />
                      <span className="truncate">{device.location}</span>
                    </div>
                  )}
                </div>

                {/* Bottom Footer */}
                <div className="pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-gray-500">
                    <Cpu size={13} className="text-indigo-500" />
                    <span className="font-semibold text-gray-800">
                      {device.acquisitions_count ?? 0}
                    </span>
                    <span>acquisitions</span>
                  </div>

                  <span className="text-indigo-600 font-semibold group-hover:translate-x-0.5 transition-transform flex items-center gap-1 text-[11px]">
                    <span>Inspect</span>
                    <ArrowRight size={13} />
                  </span>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Device Dialog */}
      <AddDeviceDialog
        caseId={caseIdentifier!}
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onDeviceCreated={loadDevices}
      />

    </div>
  );
};
