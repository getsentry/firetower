import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Spinner} from './Spinner';

const buttonVariants = cva(
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
          'bg-white',
          'dark:bg-neutral-700',
          'border',
          'border-gray-200',
          'dark:border-neutral-700',
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
      size: {
        default: 'px-space-md py-space-sm h-8',
        sm: 'px-space-sm h-7 text-xs',
        lg: 'px-space-lg h-10',
        icon: 'h-8 w-8 p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
    },
  }
);

interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  ref?: React.Ref<HTMLButtonElement>;
}

const Button = ({
  variant,
  size,
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
      className={cn(buttonVariants({variant, size, className}))}
      {...props}
    >
      {loading ? <Spinner size="sm" /> : children}
    </button>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export {Button, buttonVariants, type ButtonProps};
