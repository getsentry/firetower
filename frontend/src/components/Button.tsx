import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Spinner} from './Spinner';

const button = cva(
  [
    'inline-flex',
    'items-center',
    'justify-center',
    'transition-all',
    'cursor-pointer',
    'select-none',
    'focus:outline-auto',
    'disabled:opacity-50',
    'disabled:cursor-not-allowed',
  ],
  {
    variants: {
      variant: {
        primary: [
          'gap-space-xs',
          'px-space-md',
          'py-space-sm',
          'rounded-radius-md',
          'font-medium',
          'text-sm',
          'w-16',
          'h-8',
          'bg-background-accent-vibrant',
          'text-content-on-vibrant-light',
          'hover:opacity-90',
          'disabled:hover:opacity-50',
        ],
        secondary: [
          'gap-space-xs',
          'px-space-md',
          'py-space-sm',
          'rounded-radius-md',
          'font-medium',
          'text-sm',
          'w-16',
          'h-8',
          'bg-white',
          'text-content-primary',
          'hover:bg-background-transparent-neutral-muted',
        ],
        icon: [
          'p-space-xs',
          'rounded-radius-sm',
          'text-content-secondary',
          'hover:text-content-primary',
          'hover:bg-background-transparent-neutral-muted',
        ],
        close: [
          'p-0.5',
          'rounded-radius-sm',
          'text-content-disabled',
          'hover:text-content-primary',
          'hover:bg-background-transparent-neutral-muted',
        ],
      },
    },
    defaultVariants: {
      variant: 'primary',
    },
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  loading?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
}

const Button = ({
  variant,
  loading,
  disabled,
  children,
  className,
  ref,
  ...props
}: ButtonProps) => {
  return (
    <button
      ref={ref}
      type="button"
      disabled={disabled || loading}
      className={cn(button({variant, className}))}
      {...props}
    >
      {loading ? <Spinner size="sm" /> : children}
    </button>
  );
};

export {Button, type ButtonProps};
