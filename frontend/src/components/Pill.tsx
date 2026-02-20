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
        Active: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
        Mitigated: ['bg-background-warning-vibrant', 'text-content-on-vibrant-light'],
        Postmortem: ['bg-background-accent-vibrant', 'text-content-on-vibrant-light'],
        Done: ['bg-background-success-vibrant', 'text-content-on-vibrant-light'],
        Cancelled: ['bg-background-secondary', 'text-content-secondary'],
        // Severity variants
        P0: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
        P1: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
        P2: ['bg-background-warning-vibrant', 'text-content-on-vibrant-light'],
        P3: ['bg-background-accent-vibrant', 'text-content-on-vibrant-light'],
        P4: ['bg-background-secondary', 'text-content-primary'],
        // Service tier variants
        T0: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
        T1: ['bg-background-warning-vibrant', 'text-content-on-vibrant-light'],
        T2: ['bg-background-accent-vibrant', 'text-content-on-vibrant-light'],
        T3: ['bg-background-success-vibrant', 'text-content-on-vibrant-light'],
        T4: ['bg-background-secondary', 'text-content-primary'],
        // Other variants
        private: ['bg-background-danger-vibrant', 'text-content-on-vibrant-light'],
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
