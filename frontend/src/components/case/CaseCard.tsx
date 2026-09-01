import { motion } from 'framer-motion';
import { FolderOpen, User, Calendar, ChevronRight } from 'lucide-react';
import type { Case } from '../../types/case';
import { Badge } from '../ui/Badge';
import { fadeSlideUp, cardHover, cardTap } from '../../lib/motion';

interface CaseCardProps {
  caseData: Case;
  isSelected: boolean;
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
}

function statusVariant(status: string): 'active' | 'archived' | 'open' | 'closed' | 'default' {
  switch (status) {
    case 'ACTIVE': return 'active';
    case 'ARCHIVED': return 'archived';
    case 'OPEN': return 'open';
    case 'CLOSED': return 'closed';
    default: return 'default';
  }
}

function roleVariant(role?: string): 'admin' | 'investigator' | 'viewer' | 'default' {
  switch (role) {
    case 'ADMIN': return 'admin';
    case 'INVESTIGATOR': return 'investigator';
    case 'VIEWER': return 'viewer';
    default: return 'default';
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function CaseCard({ caseData, isSelected, onSelect, onOpen }: CaseCardProps) {
  return (
    <motion.div
      layout
      variants={fadeSlideUp}
      whileHover={cardHover}
      whileTap={cardTap}
      onClick={() => onSelect(caseData.id)}
      onDoubleClick={() => onOpen(caseData.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          if (isSelected) onOpen(caseData.id);
          else onSelect(caseData.id);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`Case ${caseData.case_identifier}: ${caseData.name}`}
      aria-pressed={isSelected}
      className={`
        group relative bg-white rounded-lg border p-5 cursor-pointer
        transition-colors duration-150 outline-none
        focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2
        ${isSelected
          ? 'border-indigo-400 ring-1 ring-indigo-200 bg-indigo-50/30'
          : 'border-gray-200 hover:border-gray-300'
        }
      `}
    >
      {/* Case Identifier */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono text-gray-400 tracking-wide">
          {caseData.case_identifier}
        </span>
        {caseData.role && (
          <Badge variant={roleVariant(caseData.role)}>
            {caseData.role}
          </Badge>
        )}
      </div>

      {/* Case Name */}
      <h3 className="text-sm font-semibold text-gray-900 mb-3 leading-snug line-clamp-2">
        {caseData.name}
      </h3>

      {/* Metadata */}
      <div className="space-y-1.5 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <FolderOpen size={12} className="shrink-0 text-gray-400" />
          <span className="truncate">{caseData.case_type}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <User size={12} className="shrink-0 text-gray-400" />
          <span className="truncate">{caseData.admin_display_name}</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <Calendar size={12} className="shrink-0 text-gray-400" />
          <span>{formatDate(caseData.updated_at)}</span>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <Badge variant={statusVariant(caseData.status)}>
          {caseData.status}
        </Badge>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onOpen(caseData.id);
          }}
          className="
            inline-flex items-center gap-1 text-xs font-medium
            text-gray-400 hover:text-indigo-600
            opacity-0 group-hover:opacity-100 focus:opacity-100
            transition-all duration-150
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 rounded
            px-1.5 py-0.5
          "
          aria-label={`Open case ${caseData.case_identifier}`}
        >
          Open
          <ChevronRight size={12} />
        </button>
      </div>
    </motion.div>
  );
}
