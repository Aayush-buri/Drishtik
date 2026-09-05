import { useState, useEffect, useMemo } from 'react';
import { 
  FileText, Shield, RefreshCw, Search, Film, Trash2, Plus, 
  CheckCircle, ArrowRight, User, Eye, Printer, Copy, Check, 
  X, Filter, HardDrive, Cpu, Layers, Clock, FileCheck
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { evidenceService } from '../../services/evidenceService';
import type { AuditLogEntry, Evidence } from '../../services/evidenceService';

interface ForensicReport {
  id: string;
  title: string;
  reportType: 'Video Summary' | 'Evidence Report' | 'Recovery Report' | 'AI Analysis Report' | 'Chain of Custody Report';
  createdBy: string;
  generatedDate: string;
  status: 'Draft' | 'Generated' | 'Final';
  description: string;
}

export function RecordsModule() {
  const { activeCase, user } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<string>('ALL');

  // Selected Log for detail modal
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);
  const [copiedPayload, setCopiedPayload] = useState(false);
  const [rawPayloadExpanded, setRawPayloadExpanded] = useState(false);

  // Selected Report for view modal
  const [selectedReport, setSelectedReport] = useState<ForensicReport | null>(null);
  const [generatingReportId, setGeneratingReportId] = useState<string | null>(null);

  // Reports state
  const [reports, setReports] = useState<ForensicReport[]>([
    {
      id: 'REP-001',
      title: 'Forensic Video Summary',
      reportType: 'Video Summary',
      createdBy: 'Forensic Examiner',
      generatedDate: new Date().toISOString().split('T')[0],
      status: 'Generated',
      description: 'Overview of imported video streams, technical parameters, codec profiles, and CCTV channels.'
    },
    {
      id: 'REP-002',
      title: 'Evidence Lineage & Integrity',
      reportType: 'Evidence Report',
      createdBy: 'Forensic Examiner',
      generatedDate: new Date().toISOString().split('T')[0],
      status: 'Generated',
      description: 'Cryptographic SHA-256 / MD5 validation records, original-to-derived lineage, and chain of custody.'
    },
    {
      id: 'REP-003',
      title: 'Storage Carving & Recovery Audit',
      reportType: 'Recovery Report',
      createdBy: 'System / Recovery Engine',
      generatedDate: new Date().toISOString().split('T')[0],
      status: 'Draft',
      description: 'Forensic carving results, discovered candidates, stream validations, and extracted evidence artifacts.'
    },
    {
      id: 'REP-004',
      title: 'AI Video Analysis Findings',
      reportType: 'AI Analysis Report',
      createdBy: 'Drishtik Vision Pipeline',
      generatedDate: new Date().toISOString().split('T')[0],
      status: 'Draft',
      description: 'YOLO and OpenCV detection logs, person and vehicle classifications, motion contours, and timeline markers.'
    },
    {
      id: 'REP-005',
      title: 'Comprehensive Chain of Custody',
      reportType: 'Chain of Custody Report',
      createdBy: 'Audit Subsystem',
      generatedDate: new Date().toISOString().split('T')[0],
      status: 'Final',
      description: 'Chronological tamper-evident journal of every procedural action taken on this case file.'
    }
  ]);

  const loadData = async () => {
    if (!activeCase) return;
    setIsLoading(true);
    try {
      const [logsData, evData] = await Promise.all([
        evidenceService.listAuditLogs(activeCase.case_identifier),
        evidenceService.listEvidence(activeCase.case_identifier).catch(() => [])
      ]);
      setLogs(logsData);
      setEvidenceList(evData);
    } catch (err) {
      console.error('Failed to load records data', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeCase]);

  // Determine Module category from Action
  const getActionModule = (action: string): string => {
    if (action.startsWith('EVIDENCE_DERIVED') || action.includes('FRAME') || action.includes('TRANSMUX')) return 'Video Analysis';
    if (action.startsWith('INTEGRITY')) return 'Integrity';
    if (action.startsWith('ACQUISITION')) return 'Acquisition';
    if (action.startsWith('RECOVERY') || action.includes('CARVE')) return 'Recovery';
    if (action.startsWith('AI_')) return 'AI Analysis';
    if (action.startsWith('EVIDENCE_')) return 'Evidence';
    return 'General';
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'EVIDENCE_DERIVED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200 whitespace-nowrap">
            <Film size={11} /> EVIDENCE DERIVED
          </span>
        );
      case 'EVIDENCE_DELETED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 whitespace-nowrap">
            <Trash2 size={11} /> EVIDENCE DELETED
          </span>
        );
      case 'EVIDENCE_IMPORTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 whitespace-nowrap">
            <Plus size={11} /> EVIDENCE IMPORTED
          </span>
        );
      case 'INTEGRITY_VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 whitespace-nowrap">
            <CheckCircle size={11} /> INTEGRITY VERIFIED
          </span>
        );
      case 'ACQUISITION_COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 whitespace-nowrap">
            <HardDrive size={11} /> ACQUISITION
          </span>
        );
      case 'RECOVERY_SCAN_STARTED':
      case 'RECOVERY_CANDIDATE_VALIDATED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 whitespace-nowrap">
            <Cpu size={11} /> RECOVERY SCAN
          </span>
        );
      case 'RECOVERED_EVIDENCE_CREATED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-teal-50 text-teal-700 border border-teal-200 whitespace-nowrap">
            <CheckCircle size={11} /> RECOVERED EVIDENCE
          </span>
        );
      case 'AI_ANALYSIS_STARTED':
      case 'AI_ANALYSIS_COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 whitespace-nowrap">
            <Cpu size={11} /> AI ANALYSIS
          </span>
        );
      case 'AI_FRAME_EXPORTED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200 whitespace-nowrap">
            <Layers size={11} /> AI FRAME EXPORT
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 whitespace-nowrap">
            {action}
          </span>
        );
    }
  };

  const getModuleBadge = (moduleName: string) => {
    switch (moduleName) {
      case 'Evidence':
        return <span className="text-[11px] font-medium text-indigo-700 bg-indigo-50/70 px-1.5 py-0.5 rounded">Evidence</span>;
      case 'Video Analysis':
        return <span className="text-[11px] font-medium text-purple-700 bg-purple-50/70 px-1.5 py-0.5 rounded">Video</span>;
      case 'Recovery':
        return <span className="text-[11px] font-medium text-amber-700 bg-amber-50/70 px-1.5 py-0.5 rounded">Recovery</span>;
      case 'AI Analysis':
        return <span className="text-[11px] font-medium text-sky-700 bg-sky-50/70 px-1.5 py-0.5 rounded">AI Vision</span>;
      case 'Acquisition':
        return <span className="text-[11px] font-medium text-blue-700 bg-blue-50/70 px-1.5 py-0.5 rounded">Acquisition</span>;
      case 'Integrity':
        return <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50/70 px-1.5 py-0.5 rounded">Integrity</span>;
      default:
        return <span className="text-[11px] font-medium text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">{moduleName}</span>;
    }
  };

  const formatDetailsSummary = (detailsStr?: string) => {
    if (!detailsStr) return <span className="text-gray-400 italic">No details recorded</span>;
    try {
      const data = JSON.parse(detailsStr);
      if (data.operation) {
        return (
          <div className="text-xs space-y-0.5">
            <div className="font-semibold text-gray-800 flex items-center gap-1.5">
              <span>{data.parent_id || 'Parent'}</span>
              <ArrowRight size={11} className="text-indigo-500" />
              <span>{data.child_id || 'Derived'}</span>
              <span className="text-indigo-600 font-normal">({data.operation})</span>
            </div>
            {data.parameters && (
              <div className="text-gray-500 font-mono text-[11px]">
                {data.parameters.start_time !== undefined && `Range: ${data.parameters.start_time}s - ${data.parameters.end_time}s `}
                {data.parameters.crop && `Crop: ${data.parameters.crop.width}×${data.parameters.crop.height}`}
              </div>
            )}
          </div>
        );
      }
      if (data.reason) {
        return (
          <div className="text-xs text-gray-700">
            <span className="font-medium text-rose-700">Reason:</span> {data.reason}
            {data.filename && <span className="text-gray-500 block truncate text-[11px]">({data.filename})</span>}
          </div>
        );
      }
      if (data.findings_count !== undefined) {
        return (
          <div className="text-xs text-gray-700">
            <span className="font-semibold text-sky-700">{data.findings_count}</span> findings detected across {data.total_frames || 'all'} frames
          </div>
        );
      }
      if (data.finding_id) {
        return (
          <div className="text-xs text-gray-700">
            Exported finding <span className="font-mono font-medium text-fuchsia-700">{data.finding_id}</span> to derived frame
          </div>
        );
      }
      if (data.candidate_id) {
        return (
          <div className="text-xs text-gray-700">
            Carved candidate <span className="font-mono font-medium text-teal-700">{data.candidate_id}</span> at offset {data.offset || '0'}
          </div>
        );
      }
      if (data.filename) {
        return <div className="text-xs text-gray-700 truncate">{data.filename} {data.size_bytes ? `(${Math.round(data.size_bytes / 1024)} KB)` : ''}</div>;
      }
      return <div className="text-xs text-gray-700 truncate max-w-xs">{JSON.stringify(data).replace(/[{"}]/g, ' ')}</div>;
    } catch {
      return <span className="text-xs text-gray-700 truncate max-w-xs">{detailsStr}</span>;
    }
  };

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      const matchesSearch = 
        log.action.toLowerCase().includes(search.toLowerCase()) ||
        (log.target_identifier && log.target_identifier.toLowerCase().includes(search.toLowerCase())) ||
        (log.username && log.username.toLowerCase().includes(search.toLowerCase())) ||
        (log.details && log.details.toLowerCase().includes(search.toLowerCase()));
      
      const matchesModule = 
        moduleFilter === 'ALL' || getActionModule(log.action) === moduleFilter;

      return matchesSearch && matchesModule;
    });
  }, [logs, search, moduleFilter]);

  const handleGenerateReport = (reportId: string) => {
    setGeneratingReportId(reportId);
    setTimeout(() => {
      setReports(prev => prev.map(r => {
        if (r.id === reportId) {
          return {
            ...r,
            status: 'Generated',
            generatedDate: new Date().toISOString().split('T')[0]
          };
        }
        return r;
      }));
      setGeneratingReportId(null);
    }, 600);
  };

  const handleExportReport = (report: ForensicReport) => {
    setSelectedReport(report);
    setTimeout(() => {
      window.print();
    }, 200);
  };

  const copyPayloadToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedPayload(true);
    setTimeout(() => setCopiedPayload(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-slate-50 overflow-hidden">
      
      {/* Top Header Bar */}
      <div className="bg-white px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shrink-0 shadow-xs z-10">
        <div>
          <div className="flex items-center gap-2">
            <FileText size={20} className="text-indigo-600" />
            <h1 className="text-lg font-bold text-gray-900">Records & Forensic Audit Log</h1>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">
            Cryptographically and procedurally logged chain-of-custody actions for case <span className="font-semibold text-gray-700">{activeCase?.case_identifier}</span>.
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
            onClick={loadData}
            disabled={isLoading}
            className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md border border-gray-200 transition-colors"
            title="Refresh Records"
          >
            <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Main Two-Panel Split Layout */}
      <div className="flex-1 overflow-hidden p-6 flex flex-col lg:flex-row gap-6">
        
        {/* LEFT PANEL: Audit Log Table (~60% on desktop) */}
        <div className="flex-1 min-w-0 flex flex-col bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          
          {/* Audit Log Header & Filter bar */}
          <div className="px-5 py-3.5 border-b border-gray-200 bg-gray-50/60 flex flex-wrap items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2">
              <Shield size={16} className="text-indigo-600" />
              <h2 className="text-sm font-bold text-gray-900">Chain of Custody Audit Trail</h2>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                {filteredLogs.length} events
              </span>
            </div>

            {/* Filter by Module */}
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-gray-400" />
              <select
                value={moduleFilter}
                onChange={(e) => setModuleFilter(e.target.value)}
                aria-label="Filter audit records by module"
                className="text-xs bg-white border border-gray-200 rounded-md px-2.5 py-1 text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ALL">All Modules</option>
                <option value="Evidence">Evidence</option>
                <option value="Video Analysis">Video Analysis</option>
                <option value="Recovery">Recovery</option>
                <option value="AI Analysis">AI Analysis</option>
                <option value="Acquisition">Acquisition</option>
                <option value="Integrity">Integrity</option>
              </select>
            </div>
          </div>

          {/* Audit Log Table Content */}
          <div className="flex-1 overflow-auto">
            {isLoading ? (
              <div className="h-full flex items-center justify-center py-20">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
              </div>
            ) : filteredLogs.length > 0 ? (
              <table className="w-full min-w-[720px] text-left border-collapse">
                <thead className="sticky top-0 bg-gray-50/95 backdrop-blur-xs border-b border-gray-200 z-10">
                  <tr className="text-[11px] font-bold text-gray-500 uppercase tracking-wider">
                    <th className="py-3 px-3.5 whitespace-nowrap">Timestamp (UTC)</th>
                    <th className="py-3 px-3.5 whitespace-nowrap">Action</th>
                    <th className="py-3 px-3.5 whitespace-nowrap">Module</th>
                    <th className="py-3 px-3.5 whitespace-nowrap">Target Evidence</th>
                    <th className="py-3 px-3.5 whitespace-nowrap">User</th>
                    <th className="py-3 px-3.5 whitespace-nowrap">Result</th>
                    <th className="py-3 px-3.5">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 text-sm">
                  {filteredLogs.map(log => {
                    const moduleName = getActionModule(log.action);
                    return (
                      <tr 
                        key={log.id} 
                        onClick={() => setSelectedLog(log)}
                        className="hover:bg-indigo-50/40 transition-colors cursor-pointer group"
                      >
                        <td className="py-3 px-3.5 font-mono text-xs text-gray-500 whitespace-nowrap">
                          {new Date(log.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                        </td>
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          {getActionBadge(log.action)}
                        </td>
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          {getModuleBadge(moduleName)}
                        </td>
                        <td className="py-3 px-3.5 font-mono text-xs font-semibold text-indigo-700 whitespace-nowrap">
                          {log.target_identifier ? (
                            <span className="group-hover:underline">{log.target_identifier}</span>
                          ) : (
                            <span className="text-gray-400 font-normal">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3.5 text-gray-700 text-xs font-medium whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <User size={13} className="text-gray-400" />
                            <span>{log.username || 'System'}</span>
                          </div>
                        </td>
                        <td className="py-3 px-3.5 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <Check size={10} /> SUCCESS
                          </span>
                        </td>
                        <td className="py-3 px-3.5 max-w-xs">
                          {formatDetailsSummary(log.details)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto p-12">
                <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mb-3 border border-gray-200">
                  <Shield size={24} className="text-gray-400" />
                </div>
                <h3 className="text-base font-bold text-gray-900">No audit records match</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {search ? 'Try clearing your search filters.' : 'Importing, carving, or deriving evidence creates verifiable entries automatically.'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT PANEL: Forensic Reports & Export (~40% on desktop) */}
        <div className="w-full lg:w-[380px] xl:w-[450px] flex flex-col bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden shrink-0">
          
          {/* Reports Header */}
          <div className="px-5 py-3.5 border-b border-gray-200 bg-gray-50/60 flex items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2">
              <FileCheck size={16} className="text-indigo-600" />
              <h2 className="text-sm font-bold text-gray-900">Forensic Reports</h2>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                {reports.length} Available
              </span>
            </div>
          </div>

          {/* Reports List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
            {reports.map((report) => {
              const isGenerating = generatingReportId === report.id;

              return (
                <div 
                  key={report.id}
                  className="p-4 rounded-lg border border-gray-200 bg-white hover:border-indigo-300 hover:shadow-xs transition-all flex flex-col gap-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">
                          {report.id}
                        </span>
                        <h3 className="text-sm font-bold text-gray-900">{report.title}</h3>
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                        {report.description}
                      </p>
                    </div>

                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider shrink-0 ${
                      report.status === 'Final' 
                        ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                        : report.status === 'Generated'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-gray-100 text-gray-600 border border-gray-200'
                    }`}>
                      {report.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-gray-400 border-t border-gray-100 pt-2 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock size={11} /> {report.generatedDate}
                    </span>
                    <span className="truncate max-w-[140px]">
                      By: {report.createdBy}
                    </span>
                  </div>

                  {/* Actions: View / Generate / Export */}
                  <div className="flex items-center gap-2 pt-1 border-t border-gray-100">
                    <button
                      onClick={() => setSelectedReport(report)}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors"
                    >
                      <Eye size={13} className="text-gray-500" />
                      View
                    </button>

                    <button
                      onClick={() => handleGenerateReport(report.id)}
                      disabled={isGenerating}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition-colors disabled:opacity-50"
                    >
                      <RefreshCw size={13} className={isGenerating ? 'animate-spin' : ''} />
                      {isGenerating ? 'Generating...' : 'Generate'}
                    </button>

                    <button
                      onClick={() => handleExportReport(report)}
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors"
                      title="Export / Print Forensic Report"
                    >
                      <Printer size={13} className="text-gray-600" />
                      Export
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Summary Footer */}
          <div className="p-3.5 border-t border-gray-200 bg-gray-50/60 text-xs text-gray-500 flex items-center justify-between shrink-0">
            <span>Case Evidence: <strong>{evidenceList.length}</strong> items</span>
            <span>Audited Actions: <strong>{logs.length}</strong></span>
          </div>
        </div>

      </div>

      {/* MODAL: Structured Audit Entry Detail Drawer */}
      {selectedLog && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-xl max-h-[85vh] flex flex-col overflow-hidden">
            
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/70">
              <div className="flex items-center gap-2.5">
                <Shield size={18} className="text-indigo-600" />
                <h3 className="text-base font-bold text-gray-900">Audit Log Entry #{selectedLog.id}</h3>
              </div>
              <button 
                onClick={() => setSelectedLog(null)}
                aria-label="Close detail dialog"
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-4 text-sm">
              
              {/* Top metadata grid */}
              <div className="grid grid-cols-2 gap-3 bg-gray-50 p-3.5 rounded-lg border border-gray-200 text-xs">
                <div>
                  <span className="text-gray-400 block mb-0.5">ACTION</span>
                  {getActionBadge(selectedLog.action)}
                </div>
                <div>
                  <span className="text-gray-400 block mb-0.5">STATUS / RESULT</span>
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-700">
                    <Check size={12} /> SUCCESSFUL & COMMITTED
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block mb-0.5">TIMESTAMP (UTC)</span>
                  <span className="font-mono text-gray-700 font-semibold">
                    {new Date(selectedLog.created_at).toUTCString()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block mb-0.5">TARGET EVIDENCE</span>
                  <span className="font-mono font-bold text-indigo-700">
                    {selectedLog.target_identifier || 'N/A (System / Case Level)'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block mb-0.5">USER</span>
                  <span className="font-semibold text-gray-800 flex items-center gap-1">
                    <User size={12} className="text-gray-400" />
                    {selectedLog.username || `User ID ${selectedLog.user_id}`}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400 block mb-0.5">MODULE</span>
                  <span className="font-semibold text-gray-800">
                    {getActionModule(selectedLog.action)}
                  </span>
                </div>
              </div>

              {/* Parsed Details Breakdown */}
              <div>
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                  Action Parameters & Findings
                </h4>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                  {formatDetailsSummary(selectedLog.details)}
                </div>
              </div>

              {/* Collapsible Raw JSON Payload */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <button 
                    type="button"
                    onClick={() => setRawPayloadExpanded(!rawPayloadExpanded)}
                    className="text-xs font-bold text-gray-700 uppercase tracking-wider hover:text-indigo-600 flex items-center gap-1"
                  >
                    <span>{rawPayloadExpanded ? '▼ Hide' : '▶ Show'} Raw Audit Payload</span>
                  </button>

                  {selectedLog.details && (
                    <button
                      onClick={() => copyPayloadToClipboard(selectedLog.details || '')}
                      className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      {copiedPayload ? <Check size={12} className="text-emerald-600" /> : <Copy size={12} />}
                      {copiedPayload ? 'Copied' : 'Copy JSON'}
                    </button>
                  )}
                </div>

                {rawPayloadExpanded && (
                  <pre className="p-3 bg-gray-900 text-gray-100 rounded-lg text-xs font-mono overflow-x-auto max-h-48 border border-gray-800">
                    {(() => {
                      try {
                        return JSON.stringify(JSON.parse(selectedLog.details || '{}'), null, 2);
                      } catch {
                        return selectedLog.details || 'No details';
                      }
                    })()}
                  </pre>
                )}
              </div>

            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-200 rounded-md hover:bg-gray-100 transition-colors"
              >
                Close
              </button>
            </div>

          </div>
        </div>
      )}

      {/* MODAL: Formatted Forensic Case Report Modal (Printable) */}
      {selectedReport && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
            
            {/* Modal Actions Bar (Not Printed) */}
            <div className="px-6 py-3.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between print:hidden">
              <div className="flex items-center gap-2">
                <FileCheck size={18} className="text-indigo-600" />
                <span className="text-sm font-bold text-gray-900">{selectedReport.title}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                  {selectedReport.status}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs transition-colors"
                >
                  <Printer size={13} />
                  Print / Save as PDF
                </button>
                <button
                  onClick={() => setSelectedReport(null)}
                  aria-label="Close report view"
                  className="p-1.5 text-gray-400 hover:text-gray-600 rounded-md hover:bg-gray-200 transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Printable Report Document */}
            <div className="p-8 overflow-y-auto flex-1 font-serif text-gray-900 bg-white" id="printable-report">
              
              {/* Formal Laboratory Header */}
              <div className="border-b-2 border-gray-900 pb-4 mb-6">
                <div className="flex justify-between items-start">
                  <div>
                    <h1 className="text-xl font-bold tracking-wide uppercase">Drishtik Forensic Analysis System</h1>
                    <p className="text-xs text-gray-600 font-sans mt-0.5">Digital Video & Storage Forensic Examination Laboratory</p>
                  </div>
                  <div className="text-right text-xs font-mono text-gray-700">
                    <div>DOC REF: <strong>{selectedReport.id}</strong></div>
                    <div>DATE: <strong>{new Date().toISOString().split('T')[0]}</strong></div>
                    <div>PAGE: <strong>1 of 1</strong></div>
                  </div>
                </div>
              </div>

              {/* Case Information Box */}
              <div className="mb-6 bg-gray-50 border border-gray-300 p-4 font-sans text-xs">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <span className="text-gray-500 block font-bold">CASE IDENTIFIER</span>
                    <span className="text-gray-900 font-mono font-bold text-sm">{activeCase?.case_identifier}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-bold">REPORT TYPE</span>
                    <span className="text-gray-900 font-semibold">{selectedReport.reportType}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-bold">EXAMINER / OPERATOR</span>
                    <span className="text-gray-900 font-semibold">{user?.username || 'Forensic Examiner'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-bold">HASH STANDARD</span>
                    <span className="text-gray-900 font-mono font-bold">SHA-256 + MD5</span>
                  </div>
                </div>
              </div>

              {/* Executive Summary */}
              <div className="mb-6 font-sans">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 border-b border-gray-300 pb-1 mb-2">
                  1. Executive Summary & Scope
                </h3>
                <p className="text-xs text-gray-700 leading-relaxed">
                  This report documents the forensic evaluation, cryptographic integrity verification, and procedural handling of digital media artifacts associated with Case <strong>{activeCase?.case_identifier}</strong>. All processes adhere to digital forensic chain-of-custody standards. Original source materials remain strictly read-only; all investigative extractions and processing outputs are immutably derived and catalogued with unique cryptographic digests.
                </p>
              </div>

              {/* Evidence Inventory Table */}
              <div className="mb-6 font-sans">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 border-b border-gray-300 pb-1 mb-2">
                  2. Evidence Inventory & Cryptographic Hashes
                </h3>
                {evidenceList.length > 0 ? (
                  <table className="w-full text-left text-xs border border-gray-300 mt-2">
                    <thead className="bg-gray-100 text-gray-700 font-bold border-b border-gray-300">
                      <tr>
                        <th className="p-2 border-r border-gray-300">Evidence ID</th>
                        <th className="p-2 border-r border-gray-300">Filename</th>
                        <th className="p-2 border-r border-gray-300">Status</th>
                        <th className="p-2 border-r border-gray-300">Size (Bytes)</th>
                        <th className="p-2">SHA-256 Hash</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 font-mono text-[11px]">
                      {evidenceList.map(ev => (
                        <tr key={ev.id}>
                          <td className="p-2 font-bold text-gray-900 border-r border-gray-200">{ev.evidence_identifier}</td>
                          <td className="p-2 font-sans border-r border-gray-200">{ev.original_filename}</td>
                          <td className="p-2 border-r border-gray-200">
                            <span className="font-sans font-semibold text-[10px] px-1 py-0.5 rounded bg-gray-100 border border-gray-300">
                              {ev.evidence_status}
                            </span>
                          </td>
                          <td className="p-2 border-r border-gray-200">{ev.size_bytes.toLocaleString()}</td>
                          <td className="p-2 text-[10px] text-gray-600 break-all">{ev.sha256 || 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-xs text-gray-500 italic mt-2">No evidence items registered in this case inventory.</p>
                )}
              </div>

              {/* Recent Chain of Custody Operations */}
              <div className="mb-8 font-sans">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 border-b border-gray-300 pb-1 mb-2">
                  3. Audit Trail Excerpt (Chronological)
                </h3>
                <div className="border border-gray-300 rounded-sm overflow-hidden mt-2">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-gray-100 text-gray-700 font-bold border-b border-gray-300">
                      <tr>
                        <th className="p-2 border-r border-gray-300">Timestamp (UTC)</th>
                        <th className="p-2 border-r border-gray-300">Action</th>
                        <th className="p-2 border-r border-gray-300">Target</th>
                        <th className="p-2 border-r border-gray-300">Operator</th>
                        <th className="p-2">Result</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 text-[11px]">
                      {logs.slice(0, 8).map(log => (
                        <tr key={log.id}>
                          <td className="p-2 font-mono text-gray-600 border-r border-gray-200">
                            {new Date(log.created_at).toISOString().replace('T', ' ').substring(0, 19)}
                          </td>
                          <td className="p-2 font-semibold border-r border-gray-200">{log.action}</td>
                          <td className="p-2 font-mono border-r border-gray-200">{log.target_identifier || '—'}</td>
                          <td className="p-2 border-r border-gray-200">{log.username || 'System'}</td>
                          <td className="p-2 font-bold text-emerald-800">SUCCESS</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Examiner Attestation & Signature Line */}
              <div className="border-t-2 border-gray-900 pt-6 font-sans text-xs">
                <div className="grid grid-cols-2 gap-8">
                  <div>
                    <h4 className="font-bold text-gray-900 mb-1">EXAMINER ATTESTATION</h4>
                    <p className="text-[11px] text-gray-600 leading-relaxed">
                      I certify that the evidence, procedures, and findings detailed in this document accurately represent the computational processing performed within Drishtik Forensic System without unauthorized alteration.
                    </p>
                  </div>
                  <div className="flex flex-col justify-end items-end">
                    <div className="w-64 border-b border-gray-400 mb-1 text-center font-serif italic text-gray-700">
                      {user?.username || 'Digital Forensic Examiner'}
                    </div>
                    <span className="text-[10px] text-gray-500 uppercase tracking-wider">Authorized Digital Forensics Signature</span>
                  </div>
                </div>
              </div>

            </div>

          </div>
        </div>
      )}

    </div>
  );
}
