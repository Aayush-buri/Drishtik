import { forwardRef } from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';

interface IconButtonProps extends HTMLMotionProps<'button'> {
  icon: React.ReactNode;
  size?: 'sm' | 'md';
}

const sizeClasses = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
} as const;

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, size = 'md', className = '', ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileTap={{ scale: 0.92 }}
        className={`
          inline-flex items-center justify-center rounded-md
          text-gray-500 hover:text-gray-700 hover:bg-gray-100
          transition-colors duration-150
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1
          disabled:opacity-50 disabled:cursor-not-allowed
          ${sizeClasses[size]}
          ${className}
        `}
        {...props}
      >
        {icon}
      </motion.button>
    );
  }
);

IconButton.displayName = 'IconButton';
