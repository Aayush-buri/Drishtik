import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, UploadCloud, File, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { evidenceService } from '../../../services/evidenceService';
import { useAuth } from '../../../hooks/useAuth';

interface ImportEvidenceDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

export function ImportEvidenceDialog({ isOpen, onClose, onImportComplete }: ImportEvidenceDialogProps) {
  const { activeCase } = useAuth();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setError(null);
      setSuccess(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0]);
      setError(null);
      setSuccess(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleImport = async () => {
    if (!selectedFile || !activeCase) return;

    setIsUploading(true);
    setProgress(0);
    setError(null);

    try {
      await evidenceService.importEvidence(activeCase.case_identifier, selectedFile, (p) => {
        setProgress(p);
      });
      setSuccess(true);
      setTimeout(() => {
        onImportComplete();
        handleClose();
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to import evidence");
    } finally {
      setIsUploading(false);
    }
  };

  const handleClose = () => {
    if (isUploading) return;
    setSelectedFile(null);
    setProgress(0);
    setError(null);
    setSuccess(false);
    onClose();
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
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
          className="bg-white rounded-xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col"
        >
          <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
            <h2 className="text-lg font-semibold text-gray-900">Import Evidence</h2>
            <button onClick={handleClose} disabled={isUploading} className="text-gray-400 hover:text-gray-600 disabled:opacity-50 transition-colors">
              <X size={20} />
            </button>
          </div>

          <div className="p-6">
            {!selectedFile ? (
              <div 
                className="border-2 border-dashed border-gray-200 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:bg-gray-50 transition-colors cursor-pointer"
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => fileInputRef.current?.click()}
              >
                <input 
                  type="file" 
                  className="hidden" 
                  ref={fileInputRef} 
                  onChange={handleFileChange} 
                  accept="video/*,image/*,.dav"
                />
                <div className="h-12 w-12 rounded-full bg-indigo-50 flex items-center justify-center mb-4">
                  <UploadCloud size={24} className="text-indigo-600" />
                </div>
                <p className="text-sm font-medium text-gray-900 mb-1">Click to upload or drag and drop</p>
                <p className="text-xs text-gray-500">Video or Image files (mp4, avi, dav, jpg, png)</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-start gap-4 p-4 rounded-lg border border-gray-200 bg-gray-50">
                  <div className="p-2 bg-white rounded-md border border-gray-100 shadow-sm">
                    <File size={24} className="text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{selectedFile.name}</p>
                    <p className="text-xs text-gray-500 mt-1">{formatSize(selectedFile.size)} • {selectedFile.type || 'Unknown type'}</p>
                  </div>
                  {!isUploading && !success && (
                    <button onClick={() => setSelectedFile(null)} className="text-gray-400 hover:text-gray-600">
                      <X size={16} />
                    </button>
                  )}
                </div>

                {isUploading && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-gray-700 flex items-center gap-1.5">
                        <Loader2 size={12} className="animate-spin text-indigo-600" />
                        {progress < 100 ? 'Uploading and Hashing...' : 'Finalizing Storage...'}
                      </span>
                      <span className="text-gray-900">{progress}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }} 
                        animate={{ width: `${progress}%` }} 
                        className="h-full bg-indigo-600"
                      />
                    </div>
                  </div>
                )}

                {error && (
                  <div className="p-3 rounded-md bg-red-50 border border-red-100 flex items-start gap-2">
                    <AlertCircle size={16} className="text-red-600 mt-0.5 shrink-0" />
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}

                {success && (
                  <div className="p-3 rounded-md bg-emerald-50 border border-emerald-100 flex items-start gap-2">
                    <CheckCircle size={16} className="text-emerald-600 mt-0.5 shrink-0" />
                    <p className="text-sm text-emerald-700 font-medium">Import completed successfully</p>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-gray-100 bg-gray-50/50 flex justify-end gap-3">
            <button 
              type="button" 
              onClick={handleClose}
              disabled={isUploading}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50"
            >
              Cancel
            </button>
            <button 
              type="button" 
              onClick={handleImport}
              disabled={!selectedFile || isUploading || success}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 disabled:opacity-50 disabled:bg-indigo-400 inline-flex items-center gap-2"
            >
              {isUploading ? 'Importing...' : success ? 'Imported' : 'Import Evidence'}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
