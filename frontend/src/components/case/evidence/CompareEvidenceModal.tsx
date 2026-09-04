import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertOctagon, Scale, Shield } from 'lucide-react';
import { evidenceService } from '../../../services/evidenceService';
import type { CompareResponse } from '../../../services/evidenceService';
import { useAuth } from '../../../hooks/useAuth';

interface CompareEvidenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  evidenceIds: number[];
}

export function CompareEvidenceModal({ isOpen, onClose, evidenceIds }: CompareEvidenceModalProps) {
  const { activeCase } = useAuth();
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && activeCase && evidenceIds.length > 1) {
      const compare = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const res = await evidenceService.compareEvidence(activeCase.case_identifier, evidenceIds);
          setResult(res);
        } catch (err: any) {
          setError(err.response?.data?.detail || "Failed to compare evidence");
        } finally {
          setIsLoading(false);
        }
      };
      compare();
    }
  }, [isOpen, activeCase, evidenceIds]);

  if (!isOpen) return null;

  const isIdentical = result?.result === 'IDENTICAL_FILE_CONTENT';

  const formatSize = (bytes: number) => {
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="bg-white rounded-xl shadow-xl w-full max-w-3xl flex flex-col max-h-[90vh]"
        >
          <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
            <div className="flex items-center gap-2 text-gray-900 font-semibold">
              <Scale size={20} className="text-indigo-600" />
              Compare Evidence
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
              <X size={20} />
            </button>
          </div>

          <div className="p-6 overflow-y-auto">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mb-4"></div>
                <p className="text-sm text-gray-500">Comparing cryptographic hashes...</p>
              </div>
            ) : error ? (
              <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            ) : result ? (
              <div className="space-y-6">
                <div className={`p-6 rounded-xl border ${isIdentical ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'} flex items-start gap-4`}>
                  {isIdentical ? (
                    <CheckCircle className="text-emerald-600 shrink-0 mt-1" size={28} />
                  ) : (
                    <AlertOctagon className="text-red-600 shrink-0 mt-1" size={28} />
                  )}
                  <div>
                    <h3 className={`text-lg font-bold ${isIdentical ? 'text-emerald-800' : 'text-red-800'}`}>
                      {isIdentical ? 'IDENTICAL FILE CONTENT' : 'FILE CONTENT DIFFERS'}
                    </h3>
                    <p className={`text-sm mt-1 ${isIdentical ? 'text-emerald-600' : 'text-red-600'}`}>
                      SHA-256 comparison checks file content equality. {isIdentical ? 'These files are cryptographically identical.' : 'These files have different cryptographic hashes and are not identical.'}
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                    <Shield size={16} className="text-gray-400" />
                    Hash Comparison
                  </h4>
                  <div className="overflow-x-auto rounded-lg border border-gray-200">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-gray-50 text-xs uppercase text-gray-500 font-medium">
                        <tr>
                          <th className="px-4 py-3">Evidence ID</th>
                          <th className="px-4 py-3">File Name</th>
                          <th className="px-4 py-3">Size</th>
                          <th className="px-4 py-3">SHA-256 Hash</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 bg-white">
                        {result.items.map((item) => (
                          <tr key={item.evidence_id}>
                            <td className="px-4 py-3 font-medium text-gray-900">{item.evidence_id}</td>
                            <td className="px-4 py-3 text-gray-600">{item.file_name}</td>
                            <td className="px-4 py-3 text-gray-600">{formatSize(item.size_bytes)}</td>
                            <td className="px-4 py-3 font-mono text-xs text-gray-500 break-all">{item.sha256}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/50 flex justify-end">
            <button 
              type="button" 
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50"
            >
              Close
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}


