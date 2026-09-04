import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, Search as SearchIcon, Filter, Inbox, Scale, CheckSquare, 
  Trash2, AlertTriangle, ShieldAlert
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../hooks/useAuth';
import { evidenceService } from '../../../services/evidenceService';
import type { Evidence } from '../../../services/evidenceService';
import { EvidenceCard } from './EvidenceCard';
import { ImportEvidenceDialog } from './ImportEvidenceDialog';
import { CompareEvidenceModal } from './CompareEvidenceModal';

export function EvidenceModule() {
  const { activeCase, role } = useAuth();
  const navigate = useNavigate();
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  // Selection Modes
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<Set<number>>(new Set());
  const [isCompareMode, setIsCompareMode] = useState(false);
  const [isDeleteMode, setIsDeleteMode] = useState(false);
  const [selectedDeleteIds, setSelectedDeleteIds] = useState<Set<number>>(new Set());

  // Modals
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [deleteReason, setDeleteReason] = useState('');
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const canImport = role === 'ADMIN' || role === 'INVESTIGATOR';
  const canCompare = role === 'ADMIN' || role === 'INVESTIGATOR';
  const canDelete = role === 'ADMIN';

  const loadEvidence = async () => {
    if (!activeCase) return;
    setIsLoading(true);
    try {
      const data = await evidenceService.listEvidence(activeCase.case_identifier);
      setEvidenceList(data);
    } catch (err) {
      console.error('Failed to load evidence', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadEvidence();
  }, [activeCase]);

  // Handle selection for Compare
  const handleCompareSelect = (id: number) => {
    const newSet = new Set(selectedEvidenceIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedEvidenceIds(newSet);
  };

  // Handle selection for Delete
  const handleDeleteSelect = (id: number) => {
    const newSet = new Set(selectedDeleteIds);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setSelectedDeleteIds(newSet);
  };

  // Exit delete mode
  const exitDeleteMode = () => {
    setIsDeleteMode(false);
    setSelectedDeleteIds(new Set());
    setDeleteError(null);
  };

  // Execute batch delete
  const handleConfirmDelete = async () => {
    if (!activeCase || selectedDeleteIds.size === 0) return;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      await evidenceService.batchDeleteEvidence(
        activeCase.case_identifier,
        Array.from(selectedDeleteIds),
        deleteReason.trim() || 'Removed by case administrator'
      );
      setIsDeleting(false);
      setIsDeleteConfirmOpen(false);
      exitDeleteMode();
      await loadEvidence();
    } catch (err: any) {
      setIsDeleting(false);
      setDeleteError(err.message || 'Failed to remove selected evidence.');
    }
  };

  const filteredEvidence = evidenceList.filter(e => 
    e.original_filename.toLowerCase().includes(search.toLowerCase()) ||
    e.evidence_identifier.toLowerCase().includes(search.toLowerCase())
  );

  // Identify selected items and check for derived children
  const selectedItemsForDelete = evidenceList.filter(e => selectedDeleteIds.has(e.id));
  const itemsWithChildren = selectedItemsForDelete.filter(parent => {
    const activeChildren = evidenceList.filter(child => child.parent_evidence_id === parent.id);
    return activeChildren.length > 0 || (parent.active_derived_children_count ?? 0) > 0;
  });

  return (
    <div className="h-full flex flex-col relative overflow-hidden bg-gray-50">
      
      {/* Top Bar */}
      <div className="bg-white px-6 py-4 border-b border-gray-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 shadow-sm z-10">
        <div>
          <h1 className="text-lg font-bold text-gray-900">Evidence</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage and verify imported case data.</p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto flex-wrap sm:flex-nowrap">
          {/* Normal Mode Controls */}
          {!isDeleteMode ? (
            <>
              <div className="relative flex-1 sm:w-64">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                <input 
                  type="text" 
                  placeholder="Search evidence..." 
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm bg-gray-50 border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
                />
              </div>

              <button className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-md border border-gray-200 transition-colors" title="Filter Evidence">
                <Filter size={18} />
              </button>
              
              {canCompare && (
                <button 
                  onClick={() => {
                    setIsCompareMode(!isCompareMode);
                    if (isCompareMode) setSelectedEvidenceIds(new Set());
                  }}
                  className={`px-3.5 py-2 text-sm font-medium rounded-md border transition-colors flex items-center gap-2 ${
                    isCompareMode 
                      ? 'bg-indigo-100 text-indigo-800 border-indigo-200' 
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100 border-gray-200'
                  }`}
                >
                  <CheckSquare size={16} /> 
                  {isCompareMode ? 'Exit Compare' : 'Compare Mode'}
                </button>
              )}

              {/* Admin-only Delete Button */}
              {canDelete && !isCompareMode && (
                <button
                  onClick={() => {
                    setIsDeleteMode(true);
                    setSelectedDeleteIds(new Set());
                  }}
                  className="px-3.5 py-2 text-sm font-medium rounded-md border border-gray-200 text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors flex items-center gap-2"
                  title="Remove Evidence (Admin Only)"
                >
                  <Trash2 size={16} />
                  Delete Evidence
                </button>
              )}

              {isCompareMode && selectedEvidenceIds.size > 1 && (
                <motion.button 
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  onClick={() => setIsCompareOpen(true)}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 transition-colors flex items-center gap-2 shadow-sm"
                >
                  <Scale size={16} /> Run Comparison ({selectedEvidenceIds.size})
                </motion.button>
              )}

              {canImport && (
                <button 
                  onClick={() => setIsImportOpen(true)}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700 transition-colors flex items-center gap-2 shadow-sm"
                >
                  <Plus size={16} /> Import Evidence
                </button>
              )}
            </>
          ) : (
            /* Delete Mode Active Toolbar */
            <div className="flex items-center gap-3 w-full justify-between sm:justify-end">
              <div className="flex items-center gap-2 text-sm font-semibold text-red-900 bg-red-50 border border-red-200 px-3 py-1.5 rounded-md">
                <Trash2 size={16} className="text-red-600" />
                <span>Selected: {selectedDeleteIds.size}</span>
              </div>

              <button
                onClick={exitDeleteMode}
                className="px-3.5 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>

              <button
                onClick={() => setIsDeleteConfirmOpen(true)}
                disabled={selectedDeleteIds.size === 0}
                className="px-4 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-md shadow-sm transition-colors flex items-center gap-2"
              >
                <Trash2 size={16} />
                Delete Selected ({selectedDeleteIds.size})
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="h-full flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        ) : filteredEvidence.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredEvidence.map(evidence => (
              <EvidenceCard
                key={evidence.id} 
                evidence={evidence} 
                isCompareMode={isCompareMode}
                isDeleteMode={isDeleteMode}
                isSelected={isDeleteMode ? selectedDeleteIds.has(evidence.id) : selectedEvidenceIds.has(evidence.id)}
                onSelect={() => {
                  if (isDeleteMode) {
                    handleDeleteSelect(evidence.id);
                  } else if (isCompareMode) {
                    handleCompareSelect(evidence.id);
                  }
                }}
                onClick={() => {
                  if (!isCompareMode && !isDeleteMode) {
                    navigate(evidence.id.toString());
                  }
                }}
              />
            ))}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-sm mx-auto">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 border-2 border-white shadow-sm">
              <Inbox size={28} className="text-gray-400" />
            </div>
            <h3 className="text-lg font-bold text-gray-900">No evidence yet</h3>
            <p className="text-sm text-gray-500 mt-2">
              Import video or image evidence to begin analysis. Supported formats will be hashed for integrity.
            </p>
            {canImport && (
              <button 
                onClick={() => setIsImportOpen(true)}
                className="mt-6 px-4 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-md transition-colors flex items-center gap-2"
              >
                <Plus size={16} /> Import Evidence
              </button>
            )}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {isDeleteConfirmOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-xl shadow-2xl max-w-lg w-full border border-gray-200 overflow-hidden flex flex-col"
            >
              <div className="p-6">
                <div className="flex items-center gap-3 text-red-600 mb-4">
                  <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                    <ShieldAlert size={22} />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-gray-900">DELETE EVIDENCE?</h3>
                    <p className="text-xs text-gray-500">Forensic Soft-Delete & Active Case Removal</p>
                  </div>
                </div>

                <p className="text-sm text-gray-600 mb-3">
                  You are about to remove <strong>{selectedDeleteIds.size} evidence item(s)</strong> from the active case view.
                </p>

                {/* Selected Items List */}
                <div className="bg-gray-50 p-3 rounded-lg border border-gray-200 max-h-36 overflow-y-auto space-y-1.5 mb-4 text-xs font-mono">
                  {selectedItemsForDelete.map(item => (
                    <div key={item.id} className="flex items-center justify-between text-gray-800">
                      <span className="font-bold text-indigo-700">{item.evidence_identifier}</span>
                      <span className="truncate max-w-[200px] text-gray-600 font-sans">{item.original_filename}</span>
                    </div>
                  ))}
                </div>

                {/* Derived Children Lineage Warning */}
                {itemsWithChildren.length > 0 && (
                  <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 mb-4 flex items-start gap-2.5">
                    <AlertTriangle size={18} className="text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <strong className="block font-bold">Lineage Warning:</strong>
                      <span>
                        {itemsWithChildren.length === 1 ? 'An item' : `${itemsWithChildren.length} items`} selected for removal has derived child clips.
                      </span>
                      <ul className="list-disc pl-4 mt-1 space-y-0.5 font-mono text-[11px]">
                        {itemsWithChildren.map(p => (
                          <li key={p.id}>{p.evidence_identifier} ({p.original_filename})</li>
                        ))}
                      </ul>
                      <p className="mt-1 text-[11px] text-amber-800">
                        The parent evidence will be removed from the active view, but its underlying record and hashes are preserved in the archive so derived clips never lose their lineage traceability.
                      </p>
                    </div>
                  </div>
                )}

                {/* Reason Input */}
                <div className="mb-4">
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Reason for Removal (Logged in Forensic Audit Trail):
                  </label>
                  <input
                    type="text"
                    value={deleteReason}
                    onChange={(e) => setDeleteReason(e.target.value)}
                    placeholder="e.g., Duplicate acquisition, Out of scope, Corrupted source"
                    className="w-full text-xs px-3 py-2 bg-gray-50 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-red-500"
                  />
                </div>

                {deleteError && (
                  <div className="p-2.5 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 mb-3">
                    {deleteError}
                  </div>
                )}
              </div>

              {/* Modal Actions */}
              <div className="px-6 py-3.5 bg-gray-50 border-t border-gray-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsDeleteConfirmOpen(false)}
                  disabled={isDeleting}
                  className="px-4 py-2 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={isDeleting}
                  className="px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-md shadow-sm transition-colors flex items-center gap-1.5"
                >
                  {isDeleting ? 'Removing...' : 'Confirm Delete'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <ImportEvidenceDialog 
        isOpen={isImportOpen} 
        onClose={() => setIsImportOpen(false)} 
        onImportComplete={loadEvidence} 
      />

      <CompareEvidenceModal 
        isOpen={isCompareOpen} 
        onClose={() => setIsCompareOpen(false)} 
        evidenceIds={Array.from(selectedEvidenceIds)} 
      />
    </div>
  );
}

