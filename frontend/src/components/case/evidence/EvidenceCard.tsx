import { Image as ImageIcon, Video, File, ShieldCheck, ShieldAlert, GitBranch } from 'lucide-react';
import type { Evidence } from '../../../services/evidenceService';

interface EvidenceCardProps {
  isCompareMode?: boolean;
  isDeleteMode?: boolean;
  evidence: Evidence;
  isSelected: boolean;
  onSelect: () => void;
  onClick: () => void;
}

export function EvidenceCard({ 
  evidence, 
  isCompareMode = false, 
  isDeleteMode = false, 
  isSelected, 
  onSelect, 
  onClick 
}: EvidenceCardProps) {
  const isSelectionActive = isCompareMode || isDeleteMode;

  const getIcon = () => {
    switch (evidence.media_type) {
      case 'Video': return <Video size={24} className={evidence.evidence_status === 'DERIVED' ? 'text-purple-600' : 'text-indigo-600'} />;
      case 'Image': return <ImageIcon size={24} className="text-blue-600" />;
      default: return <File size={24} className="text-gray-500" />;
    }
  };

  const formatSize = (bytes: number) => {
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div 
      onClick={() => isSelectionActive ? onSelect() : onClick()}
      className={`group relative flex flex-col p-4 rounded-xl border transition-all cursor-pointer ${
        isSelected 
          ? isDeleteMode
            ? 'border-red-600 ring-2 ring-red-500 bg-red-50/20 shadow-sm'
            : 'border-indigo-600 ring-2 ring-indigo-500 bg-indigo-50/20 shadow-sm'
          : 'border-gray-200 bg-white hover:border-indigo-300 hover:shadow-sm'
      }`}
    >
      {/* Selection checkbox (Only visible in Selection Modes) */}
      {isSelectionActive && (
        <div 
          className="absolute top-3.5 left-3.5 z-10"
          onClick={(e) => { e.stopPropagation(); onSelect(); }}
        >
          <div className={`w-5 h-5 rounded border flex items-center justify-center transition-colors ${
            isSelected 
              ? isDeleteMode
                ? 'bg-red-600 border-red-600 text-white'
                : 'bg-indigo-600 border-indigo-600 text-white'
              : 'border-gray-300 bg-white group-hover:border-indigo-400'
          }`}>
            {isSelected && (
              <svg viewBox="0 0 24 24" fill="none" className="w-3.5 h-3.5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            )}
          </div>
        </div>
      )}

      {/* Status Badge in Top Right */}
      <div className="absolute top-3.5 right-3.5">
        {evidence.evidence_status === 'DERIVED' ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-purple-700 bg-purple-100 px-2 py-0.5 rounded-full border border-purple-200">
            <GitBranch size={10} /> Derived
          </span>
        ) : (
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full border border-emerald-200">
            Original
          </span>
        )}
      </div>
      
      <div className="flex items-center justify-center h-24 bg-gray-50 rounded-lg border border-gray-100 mb-3 mt-4">
        {getIcon()}
      </div>
      
      <div className="flex-1 min-w-0">
        <h3 className="text-sm font-semibold text-gray-900 truncate" title={evidence.original_filename}>
          {evidence.original_filename}
        </h3>
        
        <div className="flex items-center gap-2 mt-1">
          <span className="font-mono text-xs text-gray-500">{evidence.evidence_identifier}</span>
          {evidence.parent_evidence_identifier && (
            <span className="text-[10px] text-purple-600 font-medium truncate">
              (from {evidence.parent_evidence_identifier})
            </span>
          )}
        </div>
        
        <div className="flex flex-wrap gap-1.5 mt-3">
          <span className="inline-flex items-center text-[11px] font-medium text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
            {formatSize(evidence.size_bytes)}
          </span>
          <span className="inline-flex items-center text-[11px] font-medium text-gray-600 bg-gray-100 px-2 py-0.5 rounded">
            {evidence.media_type}
          </span>
          {evidence.derived_operation && (
            <span className="inline-flex items-center text-[11px] font-semibold text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded">
              {evidence.derived_operation}
            </span>
          )}
          {evidence.integrity_status === 'VERIFIED' && (
            <span className="inline-flex items-center text-[11px] font-medium text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded gap-1">
              <ShieldCheck size={11} /> Verified
            </span>
          )}
          {evidence.integrity_status === 'MISMATCH' && (
            <span className="inline-flex items-center text-[11px] font-medium text-red-700 bg-red-100 px-2 py-0.5 rounded gap-1">
              <ShieldAlert size={11} /> Mismatch
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
