import classNames from 'classnames';
import {extendTailwindMerge} from 'tailwind-merge';

// Create custom Tailwind Merge instance with design token class groups
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      // Background colors
      'bg-color': [
        'bg-background-primary',
        'bg-background-secondary',
        'bg-background-tertiary',
        'bg-background-accent-vibrant',
        'bg-background-danger-vibrant',
        'bg-background-success-vibrant',
        'bg-background-warning-vibrant',
        'bg-background-promotion-vibrant',
        'bg-background-overlay',
        'bg-background-transparent-accent-muted',
        'bg-background-transparent-danger-muted',
        'bg-background-transparent-neutral-muted',
        'bg-background-transparent-promotion-muted',
        'bg-background-transparent-success-muted',
        'bg-background-transparent-warning-muted',
      ],
      // Text colors
      'text-color': [
        'text-content-headings',
        'text-content-primary',
        'text-content-secondary',
        'text-content-accent',
        'text-content-danger',
        'text-content-success',
        'text-content-warning',
        'text-content-disabled',
        'text-content-on-vibrant-light',
        'text-content-on-vibrant-dark',
      ],
      // Font sizes
      'font-size': [
        'text-size-xs',
        'text-size-sm',
        'text-size-md',
        'text-size-lg',
        'text-size-xl',
        'text-size-2xl',
      ],
      // Border colors
      'border-color': [
        'border-primary',
        'border-secondary',
        'border-neutral-muted',
        'border-accent-muted',
        'border-danger-vibrant',
        'border-neutral-moderate',
        'border-neutral-vibrant',
        'border-accent-moderate',
        'border-accent-vibrant',
        'border-danger-moderate',
        'border-danger-muted',
        'border-success-moderate',
        'border-success-muted',
        'border-success-vibrant',
        'border-warning-moderate',
        'border-warning-muted',
        'border-warning-vibrant',
      ],
      // Border radius
      rounded: [
        'rounded-radius-0',
        'rounded-radius-2xs',
        'rounded-radius-xs',
        'rounded-radius-sm',
        'rounded-radius-md',
        'rounded-radius-lg',
        'rounded-radius-xl',
        'rounded-radius-2xl',
        'rounded-radius-full',
      ],
      // Padding
      p: [
        'p-space-0',
        'p-space-2xs',
        'p-space-xs',
        'p-space-sm',
        'p-space-md',
        'p-space-lg',
        'p-space-xl',
        'p-space-2xl',
        'p-space-3xl',
        'p-space-4xl',
      ],
      // Padding X
      px: ['px-space-xs', 'px-space-sm', 'px-space-md', 'px-space-lg', 'px-space-xl'],
      // Padding Y
      py: ['py-space-xs', 'py-space-sm', 'py-space-md', 'py-space-lg', 'py-space-xl'],
      // Margin
      m: [
        'm-space-xs',
        'm-space-sm',
        'm-space-md',
        'm-space-lg',
        'm-space-xl',
        'm-space-2xl',
      ],
      // Margin bottom
      mb: [
        'mb-space-xs',
        'mb-space-sm',
        'mb-space-md',
        'mb-space-lg',
        'mb-space-xl',
        'mb-space-2xl',
      ],
      // Margin top
      mt: [
        'mt-space-xs',
        'mt-space-sm',
        'mt-space-md',
        'mt-space-lg',
        'mt-space-xl',
        'mt-space-2xl',
      ],
      // Gap
      gap: [
        'gap-space-2xs',
        'gap-space-xs',
        'gap-space-sm',
        'gap-space-md',
        'gap-space-lg',
        'gap-space-xl',
      ],
      // Font weights
      'font-weight': ['font-regular', 'font-medium'],
      // Font families
      'font-family': ['font-sans', 'font-mono'],
      // Line heights
      leading: ['leading-compressed', 'leading-default', 'leading-comfortable'],
    },
  },
});

// Combines the features of classnames and tailwind-merge into one, easy-to-use
// utility. Drop in replacement for both classnames and tailwind-merge.
export function cn(...inputs: classNames.ArgumentArray) {
  return twMerge(classNames(inputs));
}
