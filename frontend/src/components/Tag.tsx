import React from 'react';
import {cn} from 'utils/cn';

interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
  action?: React.ReactNode;
  ref?: React.Ref<HTMLSpanElement>;
}

export function Tag({children, className, action, ref, ...props}: TagProps) {
  return (
    <span
      ref={ref}
      className={cn(
        'inline-flex items-center gap-space-xs',
        'px-space-md py-space-xs',
        'bg-background-tertiary',
        'dark:bg-background-secondary',
        'rounded-radius-xs',
        'text-size-sm',
        'text-content-secondary',
        className
      )}
      {...props}
    >
      <span>{children}</span>
      {action}
    </span>
  );
}
