import { cva, VariantProps } from 'class-variance-authority';
import React from 'react';

import { cn } from '../../utils/cn';

// Card styles based on mockup .card class
const card = cva([
  'bg-background-primary',
  'rounded-radius-lg', 
  'p-space-2xl',
  'shadow-sm'
]);

interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof card> {}

const CardRoot = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(card({ className }))} {...props} />
  )
);
CardRoot.displayName = 'Card';

// Card Title styles based on mockup .card-title class
const title = cva([
  'text-lg',
  'font-semibold', 
  'mb-space-xl',
  'text-content-headings'
], {
  variants: {
    size: {
      sm: ['text-sm'],
      base: ['text-base'],
      lg: ['text-lg'],
      xl: ['text-xl'],
    },
  },
  defaultVariants: {
    size: 'lg',
  },
});

interface TitleProps
  extends React.HTMLAttributes<HTMLHeadingElement>,
    VariantProps<typeof title> {}

const Title = React.forwardRef<HTMLHeadingElement, TitleProps>(
  ({ className, size, children, ...props }, ref) => (
    <h3 ref={ref} className={cn(title({ className, size }))} {...props}>
      {children}
    </h3>
  )
);
Title.displayName = 'Card.Title';

export const Card = Object.assign(CardRoot, {
  Title,
});