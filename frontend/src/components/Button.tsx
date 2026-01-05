import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Spinner} from './Spinner';

const button = cva(
  [
    'inline-flex',
    'items-center',
    'justify-center',
    'gap-space-xs',
    'px-space-md',
    'py-space-sm',
    'rounded-radius-md',
    'font-medium',
    'text-sm',
    'transition-colors',
    'cursor-pointer',
    'select-none',
    'focus:outline-auto',
    'disabled:opacity-50',
    'disabled:cursor-not-allowed',
    'w-16',
    'h-8',
  ],
  {
    variants: {
      variant: {
        primary: [
          'bg-background-accent-vibrant',
          'text-content-on-vibrant-light',
          'hover:opacity-90',
          'disabled:hover:opacity-50',
        ],
        secondary: [
          'bg-white',
          'text-content-primary',
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
