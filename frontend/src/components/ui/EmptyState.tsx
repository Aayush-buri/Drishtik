import { motion } from 'framer-motion';
import { fadeSlideUp } from '../../lib/motion';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <motion.div
      className="flex flex-col items-center justify-center py-20 px-6 text-center"
      variants={fadeSlideUp}
      initial="initial"
      animate="animate"
    >
      <div className="flex items-center justify-center w-14 h-14 rounded-xl bg-gray-100 text-gray-400 mb-4">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 max-w-sm mb-5">{description}</p>
      {action}
    </motion.div>
  );
}
