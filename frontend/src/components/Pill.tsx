import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

const pill = cva(
  [
    'inline-flex',
    'items-center',
    'justify-center',
    'px-space-lg',
    'py-space-xs',
    'rounded-radius-full',
    'text-size-sm',
    'font-medium',
    'uppercase',
    'leading-none',
    'select-none',
  ],
  {
    variants: {
      variant: {
        // Status variants
        Active: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        Mitigated: ['bg-background-transparent-warning-muted', 'text-content-warning'],
        Postmortem: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        Done: ['bg-background-transparent-success-muted', 'text-content-success'],
        // Severity variants
        P0: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
        P1: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        P2: ['bg-background-transparent-warning-muted', 'text-content-warning'],
        P3: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        P4: ['bg-background-transparent-neutral-muted', 'text-content-secondary'],
        // Other variants
        private: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        default: ['bg-background-secondary', 'text-content-secondary'],
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface PillProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof pill> {
  ref?: React.Ref<HTMLDivElement>;
}

const Pill = ({className, variant, ref, ...props}: PillProps) => {
  const {children, ...rest} = props;
  return (
    <div ref={ref} className={cn(pill({variant, className}))} {...rest}>
      {children}
    </div>
  );
};

export {Pill, type PillProps};
