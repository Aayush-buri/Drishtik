import { useState, useEffect } from 'react';
import { X, Copy, Check, Terminal, AlertTriangle } from 'lucide-react';
import { evidenceService } from '../../../services/evidenceService';
import type { HexPreviewResponse } from '../../../services/evidenceService';


interface HexPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  evidenceId: number;
  evidenceIdentifier: string;
  filename: string;
}

export function HexPreviewModal({
  isOpen,
  onClose,
  caseId,
  evidenceId,
  evidenceIdentifier,
  filename
}: HexPreviewModalProps) {
  const [data, setData] = useState<HexPreviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const fetchHex = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await evidenceService.getHexPreview(caseId, evidenceId);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Failed to retrieve binary header bytes');
      } finally {
        setIsLoading(false);
      }
    };

    fetchHex();
  }, [isOpen, caseId, evidenceId]);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (!data) return;
    const text = data.rows
      .map(r => `${r.offset}  ${r.hex_bytes.padEnd(48, ' ')}  |${r.ascii_text}|`)
      .join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fadeIn">
      <div className="bg-gray-950 border border-gray-800 rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden text-gray-100">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between bg-gray-900/60">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-950/80 border border-indigo-700/50 rounded-lg text-indigo-400">
              <Terminal size={18} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Hex Header Inspection</h3>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-gray-800 text-indigo-300 border border-gray-700">
                  {evidenceIdentifier}
                </span>
              </div>
              <p className="text-xs text-gray-400 truncate max-w-md">{filename} (First 512 Bytes)</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {data && (
              <button
                onClick={handleCopy}
                className="px-3 py-1.5 text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-md border border-gray-700 flex items-center gap-1.5 transition-colors"
                title="Copy full hex dump"
              >
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                {copied ? 'Copied' : 'Copy Dump'}
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto font-mono text-xs flex-1 bg-black/95">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-gray-400">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
              <span>Reading first 512 bytes from vault storage...</span>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-950/50 border border-red-800/80 rounded-lg text-red-300 flex items-start gap-3">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-400" />
              <div>
                <div className="font-semibold">Binary Inspection Error</div>
                <div className="text-xs text-red-300/90 mt-1">{error}</div>
              </div>
            </div>
          )}

          {data && !isLoading && (
            <div>
              {/* Header columns */}
              <div className="text-gray-500 font-bold border-b border-gray-800 pb-2 mb-3 flex text-[11px] select-none">
                <span className="w-24">OFFSET</span>
                <span className="flex-1 tracking-widest">00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F</span>
                <span className="w-40 text-right">ASCII DECODE</span>
              </div>

              {/* Rows */}
              <div className="space-y-1">
                {data.rows.map((row) => (
                  <div key={row.offset} className="flex hover:bg-gray-900/80 px-1 py-0.5 rounded transition-colors group">
                    <span className="w-24 text-indigo-400/90 select-all">{row.offset}</span>
                    <span className="flex-1 text-emerald-400/90 tracking-wider select-all">{row.hex_bytes}</span>
                    <span className="w-40 text-right text-amber-200/90 tracking-wider select-all">
                      |{row.ascii_text}|
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-gray-900 text-gray-500 text-[11px] flex items-center justify-between">
                <span>Inspected {data.total_bytes_inspected} bytes</span>
                <span className="text-gray-600">Standard ASCII (32-126); non-printable characters masked as '.'</span>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-800 bg-gray-900/60 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-md transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
