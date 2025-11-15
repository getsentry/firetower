import React from 'react';
import {cn} from 'utils/cn';

interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
}

export function Tag({children, className, ...props}: TagProps) {
  return (
    <span
      className={cn(
        'px-space-md py-space-xs',
        'bg-background-tertiary',
        'rounded-radius-xs',
        'text-size-sm',
        'text-content-secondary',
        // 'transition-all duration-200',
        // 'hover:bg-background-transparent-accent-muted hover:text-content-accent hover:-translate-y-px',
        // 'cursor-default',
        className
      )}
      {...props}
    >
      <p className="mt-[2px] mb-auto">{children}</p>
    </span>
  );
}
