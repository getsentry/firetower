import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';

import {cn} from '../utils/cn';

const card = cva([
  'bg-background-primary',
  'rounded-radius-lg',
  'p-space-2xl',
  'shadow-sm',
]);

interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof card> {}

const CardRoot = React.forwardRef<HTMLDivElement, CardProps>(
  ({className, ...props}, ref) => (
    <div ref={ref} className={cn(card({className}))} {...props} />
  )
);
CardRoot.displayName = 'Card';

const title = cva(['text-lg', 'font-semibold', 'mb-space-xl', 'text-content-headings'], {
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
  ({className, size, children, ...props}, ref) => (
    <h3 ref={ref} className={cn(title({className, size}))} {...props}>
      {children}
    </h3>
  )
);
Title.displayName = 'Card.Title';

export const Card = Object.assign(CardRoot, {
  Title,
});
