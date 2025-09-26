import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';

import {cn} from '../utils/cn';

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
    'line-height-compressed',
  ],
  {
    variants: {
      // might want to tweak how the variants work later once we try using them
      variant: {
        // Status variants
        active: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        mitigated: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        'actions-pending': [
          'bg-background-transparent-warning-muted',
          'text-content-warning',
        ],
        postmortem: ['bg-background-transparent-promotion-muted', 'text-content-danger'],
        done: ['bg-background-transparent-success-muted', 'text-content-success'],
        // Severity variants
        p0: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        p1: ['bg-background-transparent-danger-muted', 'text-content-danger'],
        p2: ['bg-background-transparent-warning-muted', 'text-content-warning'],
        p3: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        p4: ['bg-background-transparent-accent-muted', 'text-content-accent'],
        // Other variants
        private: ['bg-background-transparent-promotion-muted', 'text-content-danger'],
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
