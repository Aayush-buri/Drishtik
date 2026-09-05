import { useState, useEffect, useMemo } from 'react';
import { 
  FileText, Shield, RefreshCw, Search, Film, Trash2, Plus, 
  CheckCircle, ArrowRight, User, Eye, Printer, Copy, Check, 
  X, Filter, HardDrive, Cpu, Layers, Clock, FileCheck,
  Link2, AlertTriangle, Info, Download, FilePlus
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { evidenceService } from '../../services/evidenceService';
import type { AuditLogEntry, Evidence } from '../../services/evidenceService';
import { 
  blockchainService, 
  type BlockchainHealth, 
  type CustodyEvent, 
  type BlockchainVerificationResult, 
  type EvidenceBlockchainStatus 
} from '../../services/blockchainService';
import {
  reportService,
  type ReportSummary,
  type ReportDetail,
  type ReportVerificationResult
} from '../../services/reportService';

export function RecordsModule() {
  const { activeCase, user } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<string>('ALL');

  // Left panel view mode: Audit Trail vs Chain of Custody & Blockchain
  const [recordViewMode, setRecordViewMode] = useState<'audit' | 'custody'>('audit');
  const [custodyEvents, setCustodyEvents] = useState<CustodyEvent[]>([]);
  const [blockchainHealth, setBlockchainHealth] = useState<BlockchainHealth | null>(null);

  // Blockchain verification modal state
  const [verificationResult, setVerificationResult] = useState<BlockchainVerificationResult | null>(null);
  const [isVerifyingBlockchain, setIsVerifyingBlockchain] = useState(false);
  const [copiedHashString, setCopiedHashString] = useState<string | null>(null);

  // Selected Log for detail modal
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);
  const [selectedLogBlockchain, setSelectedLogBlockchain] = useState<EvidenceBlockchainStatus | null>(null);
  const [isLoadingLogBlockchain, setIsLoadingLogBlockchain] = useState(false);
  const [copiedPayload, setCopiedPayload] = useState(false);
  const [rawPayloadExpanded, setRawPayloadExpanded] = useState(false);

  // Real Forensic Reports state
  const [reportsList, setReportsList] = useState<ReportSummary[]>([]);
  const [isLoadingReportDetail, setIsLoadingReportDetail] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [selectedReportType, setSelectedReportType] = useState<string>('CASE_SUMMARY');
  const [examinerNotesInput, setExaminerNotesInput] = useState<string>('');
  const [exportFormatInput, setExportFormatInput] = useState<string>('PDF');
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);

  // Preview & Verification modal state
  const [selectedReportDetail, setSelectedReportDetail] = useState<ReportDetail | null>(null);
  const [reportVerificationResult, setReportVerificationResult] = useState<ReportVerificationResult | null>(null);
  const [isVerifyingReport, setIsVerifyingReport] = useState(false);

  const loadData = async () => {
    if (!activeCase) return;
    setIsLoading(true);
    try {
      const [logsData, evData, healthData, custodyData, reportsData] = await Promise.all([
        evidenceService.listAuditLogs(activeCase.case_identifier),
        evidenceService.listEvidence(activeCase.case_identifier).catch(() => []),
        blockchainService.getHealth(activeCase.case_identifier).catch(() => ({
          available: false,
          status: 'UNAVAILABLE',
          network: 'Hyperledger Fabric',
          message: 'Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.'
        })),
        blockchainService.getCustodyEvents(activeCase.case_identifier).catch(() => []),
        reportService.listReports(activeCase.case_identifier).catch(() => [])
      ]);
      setLogs(logsData);
      setEvidenceList(evData);
      setBlockchainHealth(healthData);
      setCustodyEvents(custodyData);
      setReportsList(reportsData);
    } catch (err) {
      console.error('Failed to load records data', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeCase]);

  // Query blockchain status for target evidence in selectedLog
  useEffect(() => {
    if (!selectedLog || !activeCase) {
      setSelectedLogBlockchain(null);
      return;
    }
    const ev = evidenceList.find(e => e.evidence_identifier === selectedLog.target_identifier);
    if (ev) {
      setIsLoadingLogBlockchain(true);
      blockchainService.getEvidenceStatus(activeCase.case_identifier, ev.id)
        .then(data => setSelectedLogBlockchain(data))
        .catch(() => setSelectedLogBlockchain(null))
        .finally(() => setIsLoadingLogBlockchain(false));
    } else {
      setSelectedLogBlockchain(null);
    }
  }, [selectedLog, activeCase, evidenceList]);

  const handleVerifyBlockchain = async (evidenceId: number, identifier: string) => {
    if (!activeCase) return;
    setIsVerifyingBlockchain(true);
    try {
      const res = await blockchainService.verifyEvidence(activeCase.case_identifier, evidenceId);
      setVerificationResult(res);
      loadData();
    } catch (err: any) {
      setVerificationResult({
        evidence_identifier: identifier,
        overall_status: 'UNAVAILABLE',
        current_sha256: 'Unknown',
        recorded_sha256: 'Unknown',
        reason: err?.message || 'Verification request could not be processed.',
        verified_at: new Date().toISOString(),
        blockchain_status: 'UNAVAILABLE'
      });
    } finally {
      setIsVerifyingBlockchain(false);
    }
  };

  const copyHashToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHashString(text);
    setTimeout(() => setCopiedHashString(null), 2000);
  };

  // Determine Module category from Action
  const getActionModule = (action: string): string => {
    if (action.startsWith('BLOCKCHAIN_')) return 'Blockchain';
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
      case 'BLOCKCHAIN_ANCHOR_COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 whitespace-nowrap">
            <Link2 size={11} /> BLOCKCHAIN ANCHORED
          </span>
        );
      case 'BLOCKCHAIN_ANCHOR_FAILED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 whitespace-nowrap">
            <AlertTriangle size={11} /> ANCHOR FAILED / OFFLINE
          </span>
        );
      case 'BLOCKCHAIN_INTEGRITY_VERIFIED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 whitespace-nowrap">
            <Shield size={11} /> BLOCKCHAIN VERIFIED
          </span>
        );
      case 'BLOCKCHAIN_INTEGRITY_FAILED':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 whitespace-nowrap">
            <AlertTriangle size={11} /> VERIFICATION MISMATCH
          </span>
        );
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
      case 'Blockchain':
        return <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50/70 px-1.5 py-0.5 rounded">Blockchain</span>;
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

  const filteredCustodyEvents = useMemo(() => {
    return custodyEvents.filter(event => {
      const term = search.toLowerCase();
      return (
        event.action.toLowerCase().includes(term) ||
        event.sha256.toLowerCase().includes(term) ||
        (event.actor_username && event.actor_username.toLowerCase().includes(term)) ||
        (event.previous_event_reference && event.previous_event_reference.toLowerCase().includes(term)) ||
        (event.blockchain_tx_id && event.blockchain_tx_id.toLowerCase().includes(term))
      );
    });
  }, [custodyEvents, search]);

  const handleOpenGenerateModal = () => {
    setExaminerNotesInput('');
    setSelectedReportType('CASE_SUMMARY');
    setExportFormatInput('PDF');
    setShowGenerateModal(true);
  };

  const handleGenerateReportSubmit = async () => {
    if (!activeCase) return;
    setIsGeneratingReport(true);
    try {
      const newReport = await reportService.generateReport(activeCase.case_identifier, {
        report_type: selectedReportType,
        examiner_notes: examinerNotesInput.trim() || undefined,
        format: exportFormatInput
      });
      setShowGenerateModal(false);
      setExaminerNotesInput('');
      const updatedReports = await reportService.listReports(activeCase.case_identifier);
      setReportsList(updatedReports);
      setSelectedReportDetail(newReport);
    } catch (err: any) {
      alert(err?.message || 'Failed to generate forensic report.');
    } finally {
      setIsGeneratingReport(false);
    }
  };

  const handlePreviewReport = async (reportIdentifier: string) => {
    if (!activeCase) return;
    setIsLoadingReportDetail(true);
    try {
      const detail = await reportService.getReport(activeCase.case_identifier, reportIdentifier);
      setSelectedReportDetail(detail);
    } catch (err: any) {
      alert('Failed to load report detail: ' + (err?.message || 'Unknown error'));
    } finally {
      setIsLoadingReportDetail(false);
    }
  };

  const handleExportReportDirect = (reportIdentifier: string, format: string = 'PDF') => {
    if (!activeCase) return;
    const url = reportService.getExportUrl(activeCase.case_identifier, reportIdentifier, format);
    window.open(url, '_blank');
  };

  const handleVerifyReport = async (reportIdentifier: string) => {
    if (!activeCase) return;
    setIsVerifyingReport(true);
    try {
      const res = await reportService.verifyReport(activeCase.case_identifier, reportIdentifier);
      setReportVerificationResult(res);
    } catch (err: any) {
      alert('Report integrity check failed: ' + (err?.message || 'Unknown error'));
    } finally {
      setIsVerifyingReport(false);
    }
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
          
          {/* Audit Log / Custody Header & Filter bar */}
          <div className="px-5 py-3.5 border-b border-gray-200 bg-gray-50/60 flex flex-wrap items-center justify-between gap-3 shrink-0">
            {/* View Mode Toggle Tabs */}
            <div className="flex items-center gap-1 bg-gray-200/80 p-0.5 rounded-lg border border-gray-200">
              <button
                onClick={() => setRecordViewMode('audit')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                  recordViewMode === 'audit'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Shield size={13} className="text-indigo-600" />
                <span>Audit Trail ({filteredLogs.length})</span>
              </button>
              <button
                onClick={() => setRecordViewMode('custody')}
                className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                  recordViewMode === 'custody'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Link2 size={13} className={blockchainHealth?.available ? 'text-emerald-600' : 'text-amber-600'} />
                <span>Chain of Custody & Blockchain ({filteredCustodyEvents.length})</span>
              </button>
            </div>

            {/* Filter by Module (shown when in audit mode) */}
            {recordViewMode === 'audit' && (
              <div className="flex items-center gap-2">
                <Filter size={14} className="text-gray-400" />
                <select
                  value={moduleFilter}
                  onChange={(e) => setModuleFilter(e.target.value)}
                  aria-label="Filter audit records by module"
                  className="text-xs bg-white border border-gray-200 rounded-md px-2.5 py-1 text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="ALL">All Modules</option>
                  <option value="Blockchain">Blockchain</option>
                  <option value="Evidence">Evidence</option>
                  <option value="Video Analysis">Video Analysis</option>
                  <option value="Recovery">Recovery</option>
                  <option value="AI Analysis">AI Analysis</option>
                  <option value="Acquisition">Acquisition</option>
                  <option value="Integrity">Integrity</option>
                </select>
              </div>
            )}
          </div>

          {recordViewMode === 'audit' ? (
            /* Audit Log Table Content */
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
          ) : (
            /* Chronological Chain of Custody & Blockchain View */
            <div className="flex-1 overflow-auto flex flex-col">
              {/* Blockchain Health Status Banner */}
              {blockchainHealth?.available ? (
                <div className="m-4 mb-2 p-3 bg-emerald-50/90 border border-emerald-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-emerald-950">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 animate-pulse"></span>
                    <span className="font-bold text-emerald-900">Blockchain Service: ONLINE</span>
                    <span className="text-emerald-700 font-mono text-[11px]">
                      ({blockchainHealth.network} • Channel: {blockchainHealth.channel || 'drishtikchannel'} • Blocks: #{blockchainHealth.current_block ?? 1})
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-emerald-800 font-medium">
                    <span className="bg-emerald-100/80 px-2 py-0.5 rounded border border-emerald-200">
                      Peer: {blockchainHealth.peer_endpoint || 'peer0.org1.example.com:7051'}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="m-4 mb-2 p-3.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2.5 text-xs text-amber-950">
                  <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold text-amber-950 flex items-center gap-2">
                      <span>Blockchain Service: UNAVAILABLE</span>
                      <span className="font-semibold text-[10px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-200 uppercase">OFFLINE / UNREACHABLE</span>
                    </div>
                    <p className="text-amber-800 mt-1 leading-relaxed">
                      Blockchain anchoring unavailable. Local SHA-256 integrity and audit logging remain active.
                    </p>
                  </div>
                </div>
              )}

              {/* Custody Timeline */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {isLoading ? (
                  <div className="h-full flex items-center justify-center py-20">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                  </div>
                ) : filteredCustodyEvents.length > 0 ? (
                  <div className="relative border-l-2 border-indigo-100 ml-4 pl-6 space-y-6">
                    {filteredCustodyEvents.map((event) => {
                      const evTarget = evidenceList.find(e => e.id === event.evidence_id);
                      return (
                        <div key={event.id} className="relative group">
                          {/* Timeline node icon */}
                          <div className={`absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 bg-white flex items-center justify-center ${
                            event.blockchain_status === 'ANCHORED' 
                              ? 'border-emerald-500 bg-emerald-50' 
                              : event.blockchain_status === 'UNAVAILABLE'
                                ? 'border-amber-500 bg-amber-50'
                                : 'border-indigo-400 bg-indigo-50'
                          }`}>
                            <div className={`w-1.5 h-1.5 rounded-full ${
                              event.blockchain_status === 'ANCHORED' 
                                ? 'bg-emerald-600' 
                                : event.blockchain_status === 'UNAVAILABLE'
                                  ? 'bg-amber-600'
                                  : 'bg-indigo-600'
                            }`}></div>
                          </div>

                          {/* Event Card */}
                          <div className="bg-white p-3.5 rounded-lg border border-gray-200 hover:border-indigo-300 hover:shadow-xs transition-all flex flex-col gap-2">
                            {/* Card Top Row: Timestamp, Action, Operator, Anchored badge */}
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-xs font-bold text-gray-800">
                                  {new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                </span>
                                <span className="text-[11px] text-gray-400 font-mono">
                                  ({new Date(event.timestamp).toISOString().split('T')[0]})
                                </span>
                                <span className="font-bold text-xs text-gray-900">
                                  {event.action.replace(/_/g, ' ')}
                                </span>
                              </div>

                              <div className="flex items-center gap-1.5">
                                <span className="inline-flex items-center gap-1 text-[10px] font-medium text-gray-600 bg-gray-100 px-1.5 py-0.5 rounded">
                                  <User size={10} className="text-gray-400" />
                                  {event.actor_username || `User #${event.actor_id}`}
                                </span>

                                <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded ${
                                  event.blockchain_status === 'ANCHORED'
                                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                    : event.blockchain_status === 'UNAVAILABLE'
                                      ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                      : event.blockchain_status === 'FAILED'
                                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                        : 'bg-gray-100 text-gray-600 border border-gray-200'
                                }`}>
                                  <Link2 size={10} />
                                  {event.blockchain_status === 'ANCHORED' ? 'Blockchain Anchored' : event.blockchain_status}
                                </span>
                              </div>
                            </div>

                            {/* Card Middle: Evidence ID, Previous Event Reference */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs pt-1 border-t border-gray-100">
                              <div>
                                <span className="text-gray-400 text-[10px] block">TARGET EVIDENCE</span>
                                <span className="font-mono font-bold text-indigo-700">
                                  {evTarget ? evTarget.evidence_identifier : `Evidence #${event.evidence_id}`}
                                </span>
                                {evTarget && (
                                  <span className="text-gray-500 text-[11px] block truncate">
                                    {evTarget.original_filename}
                                  </span>
                                )}
                              </div>

                              <div>
                                <span className="text-gray-400 text-[10px] block">PREVIOUS EVENT LINK</span>
                                <span className="font-mono text-[11px] text-gray-700">
                                  {event.previous_event_reference ? (
                                    <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                                      {event.previous_event_reference}
                                    </span>
                                  ) : (
                                    <span className="text-emerald-700 font-semibold italic">Root Anchor (Genesis)</span>
                                  )}
                                </span>
                              </div>
                            </div>

                            {/* SHA-256 and Transaction Hash */}
                            <div className="space-y-1 pt-1 border-t border-gray-100 text-[11px]">
                              <div className="flex items-center justify-between">
                                <span className="text-gray-500 font-medium">Recorded SHA-256:</span>
                                <button
                                  onClick={() => copyHashToClipboard(event.sha256)}
                                  className="text-indigo-600 hover:text-indigo-800 font-mono text-[10px] flex items-center gap-0.5"
                                >
                                  {copiedHashString === event.sha256 ? <span className="text-emerald-600">Copied!</span> : <><Copy size={10} /> Copy</>}
                                </button>
                              </div>
                              <div className="font-mono text-[11px] bg-slate-50 p-1.5 rounded border border-slate-200 text-gray-800 break-all">
                                {event.sha256}
                              </div>

                              {event.blockchain_tx_id && (
                                <div className="mt-1">
                                  <div className="flex items-center justify-between">
                                    <span className="text-gray-500 font-medium">Transaction ID:</span>
                                    <button
                                      onClick={() => copyHashToClipboard(event.blockchain_tx_id!)}
                                      className="text-indigo-600 hover:text-indigo-800 font-mono text-[10px] flex items-center gap-0.5"
                                    >
                                      {copiedHashString === event.blockchain_tx_id ? <span className="text-emerald-600">Copied!</span> : <><Copy size={10} /> Copy</>}
                                    </button>
                                  </div>
                                  <div className="font-mono text-[11px] bg-slate-50 p-1.5 rounded border border-slate-200 text-gray-800 break-all">
                                    {event.blockchain_tx_id}
                                    {event.blockchain_block_number !== undefined && event.blockchain_block_number !== null && (
                                      <span className="ml-2 font-sans text-gray-500">(Block #{event.blockchain_block_number})</span>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Actions bar: Verify Integrity */}
                            <div className="flex items-center justify-between pt-1 border-t border-gray-100">
                              <span className="text-[10px] font-mono text-gray-400">
                                Event ID: {event.event_identifier}
                              </span>

                              <button
                                onClick={() => handleVerifyBlockchain(event.evidence_id, event.event_identifier)}
                                disabled={isVerifyingBlockchain}
                                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded transition-colors disabled:opacity-50"
                              >
                                <Shield size={12} />
                                {isVerifyingBlockchain ? 'Verifying...' : 'Verify Integrity'}
                              </button>
                            </div>

                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto p-12">
                    <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mb-3 border border-gray-200">
                      <Link2 size={24} className="text-gray-400" />
                    </div>
                    <h3 className="text-base font-bold text-gray-900">No Chain of Custody Records</h3>
                    <p className="text-xs text-gray-500 mt-1">
                      {search ? 'No custody events match your query.' : 'Evidence import, derivation, acquisition, and recovery automatically generate cryptographic custody records.'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT PANEL: Forensic Reports & Export (~40% on desktop) */}
        <div className="w-full lg:w-[380px] xl:w-[450px] flex flex-col bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden shrink-0">
          
          {/* Reports Header */}
          <div className="px-5 py-3.5 border-b border-gray-200 bg-gray-50/60 flex items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2">
              <FileCheck size={16} className="text-indigo-600" />
              <h2 className="text-sm font-bold text-gray-900">Forensic Reports</h2>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                {reportsList.length} Generated
              </span>
            </div>

            <button
              onClick={handleOpenGenerateModal}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs transition-colors"
            >
              <FilePlus size={14} />
              Generate Report
            </button>
          </div>

          {/* Reports List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
            {reportsList.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-gray-200 rounded-xl bg-white/50">
                <div className="w-12 h-12 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 mb-3 shadow-xs">
                  <FileText size={22} />
                </div>
                <h3 className="text-sm font-bold text-gray-900 mb-1">No forensic reports generated yet</h3>
                <p className="text-xs text-gray-500 max-w-sm mb-4 leading-relaxed">
                  Generate court-admissible forensic documentation for case <strong className="text-gray-700">{activeCase?.case_identifier}</strong>. All reports include full cryptographic SHA-256 digests and audit trail provenance.
                </p>
                <button
                  onClick={handleOpenGenerateModal}
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs transition-colors"
                >
                  <FilePlus size={14} />
                  Generate First Report
                </button>
              </div>
            ) : (
              reportsList.map((report) => (
                <div 
                  key={report.id}
                  className="p-4 rounded-lg border border-gray-200 bg-white hover:border-indigo-300 hover:shadow-xs transition-all flex flex-col gap-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-[11px] font-bold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100">
                          {report.report_identifier}
                        </span>
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 uppercase">
                          {report.report_type.replace('_', ' ')}
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                          {report.format}
                        </span>
                      </div>
                      <h3 className="text-sm font-bold text-gray-900 mt-1 truncate">{report.title}</h3>
                    </div>

                    <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider shrink-0 bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {report.status}
                    </span>
                  </div>

                  {/* SHA-256 Hash Box */}
                  <div className="bg-gray-50 p-2 rounded border border-gray-200 flex items-center justify-between gap-2">
                    <div className="text-[10px] font-mono text-gray-600 truncate flex-1">
                      <span className="font-bold text-gray-400 mr-1">SHA-256:</span>
                      {report.sha256}
                    </div>
                    <button
                      onClick={() => copyPayloadToClipboard(report.sha256)}
                      className="text-gray-400 hover:text-gray-600 shrink-0 p-0.5"
                      title="Copy SHA-256 hash"
                    >
                      <Copy size={12} />
                    </button>
                  </div>

                  {/* Metadata Row */}
                  <div className="flex items-center justify-between text-[11px] text-gray-400 border-t border-gray-100 pt-2 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock size={11} /> {new Date(report.generated_at).toISOString().replace('T', ' ').substring(0, 16)}
                    </span>
                    <span>
                      {(report.file_size / 1024).toFixed(1)} KB
                    </span>
                    <span className="flex items-center gap-1">
                      <Shield size={11} />
                      {report.blockchain_status === 'ANCHORED' ? (
                        <span className="text-emerald-600 font-semibold">ANCHORED</span>
                      ) : (
                        <span className="text-gray-500">Blockchain: UNAVAILABLE</span>
                      )}
                    </span>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center gap-1.5 pt-2 border-t border-gray-100 flex-wrap">
                    <button
                      onClick={() => handlePreviewReport(report.report_identifier)}
                      disabled={isLoadingReportDetail}
                      className="flex-1 min-w-[70px] inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors disabled:opacity-50"
                      title="Preview Report"
                    >
                      <Eye size={12} className="text-gray-500" />
                      Preview
                    </button>

                    <button
                      onClick={() => handleExportReportDirect(report.report_identifier, 'PDF')}
                      className="flex-1 min-w-[80px] inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition-colors"
                      title="Download PDF"
                    >
                      <Download size={12} />
                      Export PDF
                    </button>

                    <button
                      onClick={() => handleExportReportDirect(report.report_identifier, 'JSON')}
                      className="flex-1 min-w-[80px] inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-md transition-colors"
                      title="Download JSON"
                    >
                      <Download size={12} className="text-gray-400" />
                      JSON
                    </button>

                    <button
                      onClick={() => handleVerifyReport(report.report_identifier)}
                      disabled={isVerifyingReport}
                      className="inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition-colors"
                      title="Verify SHA-256 Report Integrity"
                    >
                      <CheckCircle size={12} />
                      Verify
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Quick Summary Footer */}
          <div className="p-3.5 border-t border-gray-200 bg-gray-50/60 text-xs text-gray-500 flex items-center justify-between shrink-0">
            <span>Generated Reports: <strong>{reportsList.length}</strong></span>
            <span>Case Evidence: <strong>{evidenceList.length}</strong> items</span>
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

              {/* Hyperledger Fabric Blockchain Anchor Status (Section 8) */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                    <Link2 size={13} className="text-indigo-600" />
                    Hyperledger Fabric Blockchain Anchor
                  </h4>
                  {selectedLog.target_identifier && evidenceList.some(e => e.evidence_identifier === selectedLog.target_identifier) && (
                    <button
                      onClick={() => {
                        const ev = evidenceList.find(e => e.evidence_identifier === selectedLog.target_identifier);
                        if (ev) {
                          handleVerifyBlockchain(ev.id, ev.evidence_identifier);
                        }
                      }}
                      disabled={isVerifyingBlockchain}
                      className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded transition-colors disabled:opacity-50"
                    >
                      <Shield size={12} />
                      {isVerifyingBlockchain ? 'Verifying...' : 'Verify Integrity'}
                    </button>
                  )}
                </div>

                <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 space-y-2.5 text-xs">
                  {isLoadingLogBlockchain ? (
                    <div className="flex items-center gap-2 py-2 text-gray-500">
                      <RefreshCw size={13} className="animate-spin text-indigo-600" />
                      <span>Checking blockchain ledger anchor status...</span>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500 font-medium">Blockchain Status:</span>
                        <span className={`font-bold px-2 py-0.5 rounded text-[11px] uppercase ${
                          selectedLogBlockchain?.blockchain_status === 'ANCHORED'
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                            : selectedLogBlockchain?.blockchain_status === 'UNAVAILABLE'
                              ? 'bg-amber-100 text-amber-800 border border-amber-200'
                              : selectedLogBlockchain?.blockchain_status === 'FAILED'
                                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                : 'bg-gray-100 text-gray-700 border border-gray-200'
                        }`}>
                          {selectedLogBlockchain?.blockchain_status || (blockchainHealth?.available ? 'NOT ANCHORED' : 'UNAVAILABLE')}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 border-t border-gray-200/70">
                        <div>
                          <span className="text-gray-500 text-[10px] block">TRANSACTION ID</span>
                          <span className="font-mono text-[11px] text-gray-900 break-all">
                            {selectedLogBlockchain?.transaction_id || selectedLogBlockchain?.anchors?.[0]?.transaction_id || (
                              <span className="text-gray-400 italic">None recorded</span>
                            )}
                          </span>
                        </div>

                        <div>
                          <span className="text-gray-500 text-[10px] block">BLOCK NUMBER</span>
                          <span className="font-mono text-[11px] text-gray-900">
                            {selectedLogBlockchain?.anchors?.[0]?.block_number !== undefined
                              ? `#${selectedLogBlockchain.anchors[0].block_number}`
                              : (blockchainHealth?.current_block ? `#${blockchainHealth.current_block}` : 'N/A')}
                          </span>
                        </div>
                      </div>

                      <div className="pt-1 border-t border-gray-200/70 space-y-1.5">
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="text-gray-500">Anchor Timestamp:</span>
                          <span className="font-mono text-gray-800">
                            {selectedLogBlockchain?.anchored_at 
                              ? new Date(selectedLogBlockchain.anchored_at).toUTCString()
                              : selectedLogBlockchain?.anchors?.[0]?.timestamp
                                ? new Date(selectedLogBlockchain.anchors[0].timestamp).toUTCString()
                                : 'N/A'}
                          </span>
                        </div>

                        <div className="flex flex-col gap-0.5">
                          <span className="text-gray-500 text-[10px]">ANCHORED SHA-256</span>
                          <span className="font-mono text-[11px] bg-white p-1.5 rounded border border-gray-200 text-gray-800 break-all">
                            {selectedLogBlockchain?.sha256 || 'N/A (Off-chain local record only)'}
                          </span>
                        </div>
                      </div>
                    </>
                  )}
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

      {/* MODAL: Real Formatted Forensic Case Report Preview Modal */}
      {selectedReportDetail && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl border border-gray-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
            
            {/* Modal Actions Bar (Not Printed) */}
            <div className="px-6 py-3.5 border-b border-gray-200 bg-gray-50 flex items-center justify-between print:hidden">
              <div className="flex items-center gap-2 flex-wrap">
                <FileCheck size={18} className="text-indigo-600" />
                <span className="text-sm font-bold text-gray-900">{selectedReportDetail.title}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                  {selectedReportDetail.status}
                </span>
                <span className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-700 font-bold border border-purple-200">
                  {selectedReportDetail.format}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 rounded-md shadow-xs transition-colors"
                  title="Print this document"
                >
                  <Printer size={13} />
                  Print
                </button>
                <button
                  onClick={() => handleExportReportDirect(selectedReportDetail.report_identifier, 'PDF')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs transition-colors"
                  title="Download court-admissible PDF"
                >
                  <Download size={13} />
                  Export PDF
                </button>
                <button
                  onClick={() => handleExportReportDirect(selectedReportDetail.report_identifier, 'JSON')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 rounded-md shadow-xs transition-colors"
                  title="Download JSON data"
                >
                  <Download size={13} className="text-gray-400" />
                  JSON
                </button>
                <button
                  onClick={() => setSelectedReportDetail(null)}
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
                    <div>DOC REF: <strong>{selectedReportDetail.report_identifier}</strong></div>
                    <div>DATE: <strong>{selectedReportDetail.generated_at.substring(0, 10)}</strong></div>
                    <div>FORMAT: <strong>{selectedReportDetail.format}</strong></div>
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
                    <span className="text-gray-900 font-semibold">{selectedReportDetail.report_type.replace('_', ' ')}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-bold">EXAMINER / OPERATOR</span>
                    <span className="text-gray-900 font-semibold">{user?.username || 'Forensic Examiner'}</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block font-bold">BLOCKCHAIN ANCHOR</span>
                    <span className="text-gray-900 font-semibold">
                      {selectedReportDetail.blockchain_status === 'ANCHORED' ? (
                        <span className="text-emerald-700 font-bold">ANCHORED</span>
                      ) : (
                        <span className="text-gray-600">UNAVAILABLE</span>
                      )}
                    </span>
                  </div>
                </div>
              </div>

              {/* Examiner Notes (If provided) */}
              {selectedReportDetail.examiner_notes && (
                <div className="mb-6 font-sans">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-900 border-b border-indigo-200 pb-1 mb-2">
                    Investigator Examination Notes & Subjective Observations
                  </h3>
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded text-xs text-indigo-950 italic whitespace-pre-wrap">
                    {selectedReportDetail.examiner_notes}
                  </div>
                </div>
              )}

              {/* Evidence Table */}
              <div className="mb-6 font-sans">
                <h3 className="text-sm font-bold uppercase tracking-wider text-gray-900 border-b border-gray-300 pb-1 mb-2">
                  Evidence Inventory & Cryptographic Hashes
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
                          <td className="p-2 text-[10px] text-gray-600 break-all">{ev.sha256 || 'Unavailable'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="text-xs text-gray-500 italic mt-2">No evidence items registered in this case inventory.</p>
                )}
              </div>

              {/* SHA-256 Report Integrity Digest */}
              <div className="mb-6 font-sans bg-gray-50 p-3 rounded border border-gray-300">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-gray-700 uppercase">Document SHA-256 Digest:</span>
                  <button
                    onClick={() => copyPayloadToClipboard(selectedReportDetail.sha256)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1 font-medium"
                  >
                    <Copy size={11} /> Copy Digest
                  </button>
                </div>
                <div className="font-mono text-[11px] text-gray-800 break-all mt-1 bg-white p-2 rounded border border-gray-200">
                  {selectedReportDetail.sha256}
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

      {/* MODAL: Generate Forensic Report Dialog */}
      {showGenerateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-2xl border border-gray-200 w-full max-w-lg flex flex-col overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
              <div className="flex items-center gap-2">
                <FilePlus size={18} className="text-indigo-600" />
                <h3 className="text-base font-bold text-gray-900">Generate Forensic Report</h3>
              </div>
              <button
                onClick={() => setShowGenerateModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-200"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs">
              {/* Report Type Selector */}
              <div>
                <label className="font-bold text-gray-700 block mb-1 uppercase tracking-wider text-[11px]">
                  Select Report Type
                </label>
                <select
                  value={selectedReportType}
                  onChange={(e) => setSelectedReportType(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-gray-50 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  <option value="CASE_SUMMARY">Case Summary / Final Investigation Report (Sections A–M)</option>
                  <option value="EVIDENCE_REPORT">Evidence Lineage & Integrity Inventory</option>
                  <option value="VIDEO_SUMMARY">Unified Video Representation Report</option>
                  <option value="RECOVERY_REPORT">Forensic Video Recovery & Stream Carving Report</option>
                  <option value="AI_REPORT">AI Video Analytics & Object/Motion Findings</option>
                  <option value="CHAIN_OF_CUSTODY">Comprehensive Chronological Chain of Custody</option>
                </select>
              </div>

              {/* Format Selector */}
              <div>
                <label className="font-bold text-gray-700 block mb-1 uppercase tracking-wider text-[11px]">
                  Output Format
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {['PDF', 'HTML', 'JSON'].map((fmt) => (
                    <button
                      key={fmt}
                      type="button"
                      onClick={() => setExportFormatInput(fmt)}
                      className={`px-3 py-2 rounded-md font-semibold text-xs border transition-all ${
                        exportFormatInput === fmt
                          ? 'bg-indigo-50 border-indigo-500 text-indigo-700 ring-1 ring-indigo-500'
                          : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {fmt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Examiner Notes */}
              <div>
                <label className="font-bold text-gray-700 block mb-1 uppercase tracking-wider text-[11px]">
                  Examiner Notes & Conclusions (Optional)
                </label>
                <textarea
                  rows={4}
                  value={examinerNotesInput}
                  onChange={(e) => setExaminerNotesInput(e.target.value)}
                  placeholder="Enter examiner notes, physical evidence observations, scope limitations, or case conclusions..."
                  className="w-full p-2.5 text-xs bg-gray-50 border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Forensic Rule: Investigative notes are preserved as authored. Automated AI findings remain strictly statistical and separate.
                </p>
              </div>
            </div>

            <div className="px-6 py-3.5 border-t border-gray-200 bg-gray-50 flex items-center justify-end gap-2">
              <button
                onClick={() => setShowGenerateModal(false)}
                disabled={isGeneratingReport}
                className="px-4 py-2 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateReportSubmit}
                disabled={isGeneratingReport}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs disabled:opacity-50"
              >
                {isGeneratingReport ? <RefreshCw size={13} className="animate-spin" /> : <FilePlus size={13} />}
                {isGeneratingReport ? 'Compiling & Signing...' : 'Generate Forensic Report'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Report Integrity Verification Modal */}
      {reportVerificationResult && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-lg overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
              <div className="flex items-center gap-2">
                <CheckCircle size={18} className="text-indigo-600" />
                <h3 className="text-sm font-bold text-gray-900">Report Cryptographic Integrity</h3>
              </div>
              <button
                onClick={() => setReportVerificationResult(null)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-3.5 text-xs">
              <div className={`p-3.5 rounded-lg border flex items-center gap-3 ${
                reportVerificationResult.overall_status === 'VERIFIED'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}>
                {reportVerificationResult.overall_status === 'VERIFIED' ? (
                  <CheckCircle className="text-emerald-600 shrink-0" size={24} />
                ) : (
                  <AlertTriangle className="text-rose-600 shrink-0" size={24} />
                )}
                <div>
                  <div className="font-bold text-sm">
                    Status: {reportVerificationResult.overall_status}
                  </div>
                  <div className="text-[11px] mt-0.5">
                    {reportVerificationResult.reason}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="p-2.5 bg-gray-50 rounded border border-gray-200">
                  <span className="font-bold text-gray-500 block mb-0.5">REPORT IDENTIFIER</span>
                  <span className="font-mono text-gray-900">{reportVerificationResult.report_identifier}</span>
                </div>
                <div className="p-2.5 bg-gray-50 rounded border border-gray-200">
                  <span className="font-bold text-gray-500 block mb-0.5">CURRENT ARTIFACT SHA-256 (DISK)</span>
                  <span className="font-mono text-gray-800 break-all">{reportVerificationResult.current_sha256}</span>
                </div>
                <div className="p-2.5 bg-gray-50 rounded border border-gray-200">
                  <span className="font-bold text-gray-500 block mb-0.5">RECORDED FORENSIC SHA-256 (DATABASE)</span>
                  <span className="font-mono text-gray-800 break-all">{reportVerificationResult.recorded_sha256}</span>
                </div>
                <div className="p-2.5 bg-gray-50 rounded border border-gray-200 flex justify-between items-center">
                  <span className="font-bold text-gray-500">BLOCKCHAIN STATUS</span>
                  <span className="font-semibold text-gray-700">{reportVerificationResult.blockchain_status}</span>
                </div>
              </div>
            </div>

            <div className="px-5 py-3 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setReportVerificationResult(null)}
                className="px-4 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: 3-Point Blockchain Integrity Verification Modal */}
      {verificationResult && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50/80">
              <div className="flex items-center gap-2">
                <Shield size={18} className="text-indigo-600" />
                <h3 className="text-sm font-bold text-gray-900">Blockchain Integrity Verification</h3>
              </div>
              <button
                onClick={() => setVerificationResult(null)}
                className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 text-xs">
              <div className={`p-3.5 rounded-lg border flex items-center gap-3 ${
                verificationResult.overall_status === 'VERIFIED'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                  : verificationResult.overall_status === 'MISMATCH'
                    ? 'bg-rose-50 border-rose-200 text-rose-900'
                    : 'bg-amber-50 border-amber-200 text-amber-900'
              }`}>
                {verificationResult.overall_status === 'VERIFIED' ? (
                  <CheckCircle className="text-emerald-600 shrink-0" size={24} />
                ) : verificationResult.overall_status === 'MISMATCH' ? (
                  <AlertTriangle className="text-rose-600 shrink-0" size={24} />
                ) : (
                  <Info className="text-amber-600 shrink-0" size={24} />
                )}
                <div>
                  <div className="font-bold text-sm">
                    Status: {verificationResult.overall_status}
                  </div>
                  <div className="text-[11px] mt-0.5 leading-relaxed">
                    {verificationResult.reason}
                  </div>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-gray-700 uppercase tracking-wider mb-2 text-[11px]">
                  3-Point Forensic Hash Audit
                </h4>
                <div className="border border-gray-200 rounded-lg overflow-hidden divide-y divide-gray-200">
                  <div className="p-2.5 bg-gray-50 flex flex-col gap-1">
                    <span className="font-semibold text-gray-700">1. Current Evidence SHA-256 (Disk Live)</span>
                    <span className="font-mono text-[11px] text-gray-800 break-all bg-white p-1.5 rounded border border-gray-200">
                      {verificationResult.current_sha256}
                    </span>
                  </div>

                  <div className="p-2.5 bg-gray-50 flex flex-col gap-1">
                    <span className="font-semibold text-gray-700">2. Recorded Evidence SHA-256 (Case DB)</span>
                    <span className="font-mono text-[11px] text-gray-800 break-all bg-white p-1.5 rounded border border-gray-200">
                      {verificationResult.recorded_sha256}
                    </span>
                  </div>

                  <div className="p-2.5 bg-gray-50 flex flex-col gap-1">
                    <span className="font-semibold text-gray-700">3. Blockchain Anchor SHA-256 (Hyperledger Fabric)</span>
                    <span className="font-mono text-[11px] text-gray-800 break-all bg-white p-1.5 rounded border border-gray-200">
                      {verificationResult.anchored_sha256 || 'Not anchored / Unavailable'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 bg-gray-50 p-2.5 rounded-lg border border-gray-200 font-mono text-[11px]">
                <div>
                  <span className="text-gray-500 font-sans block text-[10px]">TRANSACTION ID</span>
                  <span className="truncate block font-semibold text-gray-800" title={verificationResult.transaction_id}>
                    {verificationResult.transaction_id || 'N/A'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 font-sans block text-[10px]">BLOCK NUMBER</span>
                  <span className="font-semibold text-gray-800">
                    {verificationResult.block_number !== undefined && verificationResult.block_number !== null ? `#${verificationResult.block_number}` : 'N/A'}
                  </span>
                </div>
              </div>

              <div className="p-3 bg-slate-100 rounded-lg border border-slate-200 text-[11px] text-slate-700 leading-relaxed">
                <strong>Forensic Scope Limitation:</strong> Blockchain verification proves data consistency and integrity of the recorded hash at timestamp. It does NOT prove the authenticity of the CCTV source recording or the truthfulness of the video content.
              </div>
            </div>

            <div className="px-5 py-3 border-t border-gray-200 bg-gray-50 flex justify-end">
              <button
                onClick={() => setVerificationResult(null)}
                className="px-4 py-1.5 text-xs font-semibold text-gray-700 bg-white border border-gray-200 rounded-md hover:bg-gray-100 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
