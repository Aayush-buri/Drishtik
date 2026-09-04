import { useState, useEffect } from 'react';
import { 
  FileText, Shield, RefreshCw, Search, Film, Trash2, Plus, 
  CheckCircle, ArrowRight, User 
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { evidenceService } from '../../services/evidenceService';
import type { AuditLogEntry } from '../../services/evidenceService';

export function RecordsModule() {
  const { activeCase } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadLogs = async () => {
    if (!activeCase) return;
    setIsLoading(true);
    try {
      const data = await evidenceService.listAuditLogs(activeCase.case_identifier);
      setLogs(data);
    } catch (err) {
      console.error('Failed to load audit logs', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [activeCase]);

  const filteredLogs = logs.filter(log => 
    log.action.toLowerCase().includes(search.toLowerCase()) ||
    (log.target_identifier && log.target_identifier.toLowerCase().includes(search.toLowerCase())) ||
    (log.username && log.username.toLowerCase().includes(search.toLowerCase())) ||
    (log.details && log.details.toLowerCase().includes(search.toLowerCase()))
  );

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'EVIDENCE_DERIVED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800 border border-purple-200">
            <Film size={12} /> EVIDENCE DERIVED
          </span>
        );
      case 'EVIDENCE_DELETED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 border border-red-200">
            <Trash2 size={12} /> EVIDENCE DELETED
          </span>
        );
      case 'EVIDENCE_IMPORTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 border border-indigo-200">
            <Plus size={12} /> EVIDENCE IMPORTED
          </span>
        );
      case 'INTEGRITY_VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle size={12} /> INTEGRITY VERIFIED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center text-[11px] font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-800 border border-gray-200">
            {action}
          </span>
        );
    }
  };

  const formatDetails = (detailsStr?: string) => {
    if (!detailsStr) return <span className="text-gray-400 italic">No details recorded</span>;
    try {
      const data = JSON.parse(detailsStr);
      if (data.operation) {
        return (
          <div className="text-xs space-y-0.5">
            <div className="font-semibold text-purple-900 flex items-center gap-1.5">
              <span>{data.parent_id || 'Parent'}</span>
              <ArrowRight size={11} className="text-purple-500" />
              <span>{data.child_id} ({data.operation})</span>
            </div>
            {data.parameters && (
              <div className="text-gray-500 font-mono text-[11px]">
                {data.parameters.start_time !== undefined && `Range: ${data.parameters.start_time}s - ${data.parameters.end_time}s `}
                {data.parameters.crop && `Crop: ${data.parameters.crop.width}x${data.parameters.crop.height}`}
              </div>
            )}
          </div>
        );
      }
      if (data.reason) {
        return (
          <div className="text-xs text-gray-700">
            <strong>Reason:</strong> {data.reason}
            {data.filename && <span className="text-gray-500 block truncate">({data.filename})</span>}
          </div>
        );
      }
      return <pre className="text-[11px] text-gray-600 truncate max-w-md">{detailsStr}</pre>;
    } catch {
      return <span className="text-xs text-gray-700">{detailsStr}</span>;
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-50 overflow-hidden">
      
      {/* Top Bar */}
      <div className="bg-white px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shadow-sm z-10">
        <div>
          <div className="flex items-center gap-2">
            <FileText size={20} className="text-indigo-600" />
            <h1 className="text-lg font-bold text-gray-900">Records & Forensic Audit Log</h1>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">
            Cryptographically and procedurally logged chain-of-custody actions for case {activeCase?.case_identifier}.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
            <input 
              type="text" 
              placeholder="Search audit trail..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-gray-50 border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
            />
          </div>

          <button 
            onClick={loadLogs}
            disabled={isLoading}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md border border-gray-200 transition-colors"
            title="Refresh Audit Logs"
          >
            <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        ) : filteredLogs.length > 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs font-bold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Target Evidence</th>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-sm">
                {filteredLogs.map(log => (
                  <tr key={log.id} className="hover:bg-gray-50/70 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {getActionBadge(log.action)}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs font-bold text-indigo-700 whitespace-nowrap">
                      {log.target_identifier || '-'}
                    </td>
                    <td className="py-3.5 px-4 text-gray-800 text-xs font-medium whitespace-nowrap flex items-center gap-1.5 mt-3.5">
                      <User size={13} className="text-gray-400" />
                      {log.username || 'System'}
                    </td>
                    <td className="py-3.5 px-4">
                      {formatDetails(log.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 border-2 border-white shadow-sm">
              <Shield size={28} className="text-gray-400" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">No audit records yet</h3>
            <p className="text-sm text-gray-500 mt-2">
              Importing, deriving, verifying, or removing evidence creates tamper-evident audit trail entries automatically.
            </p>
          </div>
        )}
      </div>

    </div>
  );
}
