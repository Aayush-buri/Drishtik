import { motion } from 'framer-motion';
import type { Case } from '../../types/case';
import { CaseCard } from './CaseCard';
import { staggerContainer } from '../../lib/motion';

interface CaseGridProps {
  cases: Case[];
  selectedCaseId: string | null;
  onSelectCase: (id: string) => void;
  onOpenCase: (id: string) => void;
}

export function CaseGrid({ cases, selectedCaseId, onSelectCase, onOpenCase }: CaseGridProps) {
  return (
    <motion.div
      className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4"
      variants={staggerContainer}
      initial="initial"
      animate="animate"
    >
      {cases.map((c) => (
        <CaseCard
          key={c.id}
          caseData={c}
          isSelected={selectedCaseId === c.id}
          onSelect={onSelectCase}
          onOpen={onOpenCase}
        />
      ))}
    </motion.div>
  );
}
