import { useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import { dialogOverlay, dialogContent } from '../../lib/motion';
import { IconButton } from './IconButton';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export function Dialog({ open, onClose, title, children, maxWidth = 'max-w-lg' }: DialogProps) {
  const contentRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      // Focus trap
      if (e.key === 'Tab' && contentRef.current) {
        const focusable = contentRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      previousFocus.current = document.activeElement as HTMLElement;
      document.addEventListener('keydown', handleKeyDown);
      // Focus first input after animation
      requestAnimationFrame(() => {
        const firstInput = contentRef.current?.querySelector<HTMLElement>('input, button');
        firstInput?.focus();
      });
      return () => document.removeEventListener('keydown', handleKeyDown);
    } else {
      previousFocus.current?.focus();
    }
  }, [open, handleKeyDown]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            className="fixed inset-0 bg-black/20 backdrop-blur-[1px]"
            variants={dialogOverlay}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            ref={contentRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            className={`relative bg-white rounded-xl shadow-xl border border-gray-200 w-full ${maxWidth} max-h-[85vh] overflow-y-auto`}
            variants={dialogContent}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">{title}</h2>
              <IconButton
                icon={<X size={16} />}
                aria-label="Close dialog"
                onClick={onClose}
                size="sm"
              />
            </div>
            <div className="px-6 py-5">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
