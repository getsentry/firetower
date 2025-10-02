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
    'leading-compressed',
  ],
  {
    variants: {
      // might want to tweak how the variants work later once we try using them
      variant: {
        // Status variants
        Active: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        Mitigated: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        'Actions Pending': [
          'bg-background-transparent-warning-muted',
          'text-content-warning',
        ],
        Postmortem: [
          'bg-background-transparent-promotion-muted',
          'text-content-promotion',
        ],
        Done: ['bg-background-transparent-success-muted', 'text-content-success'],
        // Severity variants
        P0: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        P1: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        P2: ['bg-background-transparent-warning-muted', 'text-content-warning'],
        P3: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        P4: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        // Other variants
        private: ['bg-background-transparent-promotion-muted', 'text-content-promotion'],
        default: ['bg-background-secondary', 'text-content-secondary'],
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface PillProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof pill> {}

const Pill = React.forwardRef<HTMLSpanElement, PillProps>(
  ({className, variant, ...props}, ref) => (
    <span ref={ref} className={cn(pill({variant, className}))} {...props} />
  )
);
Pill.displayName = 'Pill';

export {Pill, type PillProps};
