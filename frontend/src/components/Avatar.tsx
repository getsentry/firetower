import {cva, type VariantProps} from 'class-variance-authority';
import {cn} from 'utils/cn';

const avatar = cva(
  [
    'bg-background-tertiary',
    'text-content-secondary',
    'flex',
    'items-center',
    'justify-center',
    'rounded-full',
    'font-semibold',
    'shrink-0',
  ],
  {
    variants: {
      size: {
        sm: ['h-6', 'w-6', 'text-xs'],
        md: ['h-8', 'w-8', 'text-sm'],
        lg: ['h-10', 'w-10', 'text-base'],
        xl: ['h-12', 'w-12', 'text-lg'],
      },
    },
    defaultVariants: {
      size: 'lg',
    },
  }
);

export interface AvatarProps extends VariantProps<typeof avatar> {
  name: string;
  src?: string | null;
  alt?: string;
  className?: string;
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function Avatar({name, src, alt, size, className}: AvatarProps) {
  if (src) {
    return <img src={src} alt={alt || name} className={cn(avatar({size}), className)} />;
  }

  return (
    <div className={cn(avatar({size}), className)} style={{lineHeight: 1}}>
      {getInitials(name)}
    </div>
  );
}
