import React from 'react';
import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

const card = cva([
  'bg-background-primary',
  'rounded-radius-lg',
  'p-space-2xl',
  'shadow-sm',
]);

interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof card> {
  ref?: React.Ref<HTMLDivElement>;
}

const CardRoot = ({className, ref, ...props}: CardProps) => (
  <div ref={ref} className={cn(card({className}))} {...props} />
);

const title = cva(['text-lg', 'font-semibold', 'mb-space-xl', 'text-content-headings'], {
  variants: {
    size: {
      sm: ['text-sm'],
      base: ['text-base'],
      lg: ['text-lg'],
      xl: ['text-xl'],
      '2xl': ['text-2xl'],
    },
  },
  defaultVariants: {
    size: 'lg',
  },
});

interface TitleProps
  extends React.HTMLAttributes<HTMLHeadingElement>, VariantProps<typeof title> {
  ref?: React.Ref<HTMLHeadingElement>;
}

const Title = ({className, size, children, ref, ...props}: TitleProps) => (
  <h3 ref={ref} className={cn(title({className, size}))} {...props}>
    {children}
  </h3>
);

export const Card = Object.assign(CardRoot, {
  Title,
});
