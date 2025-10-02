import React from 'react';
import {cn} from 'utils/cn';

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-4',
};

export const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({size = 'md', className, ...props}, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'animate-spin rounded-full border-border-secondary border-t-transparent',
          sizeClasses[size],
          className
        )}
        role="status"
        aria-label="Loading"
        data-testid="spinner"
        {...props}
      >
        <span className="sr-only">Loading...</span>
      </div>
    );
  }
);
Spinner.displayName = 'Spinner';
