import {cn} from 'utils/cn';

const baseAvatarClasses = [
  'bg-background-tertiary',
  'text-content-secondary',
  'flex',
  'items-center',
  'justify-center',
  'rounded-full',
  'font-semibold',
  'shrink-0',
].join(' ');

const sizeClasses = {
  sm: 'h-7 w-7 text-sm',
  md: 'h-10 w-10 text-base',
};

export interface AvatarProps {
  name: string;
  src?: string | null;
  alt?: string;
  className?: string;
  size?: 'sm' | 'md';
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function Avatar({name, src, alt, className, size = 'md'}: AvatarProps) {
  if (!name) return null;

  const avatarClasses = cn(baseAvatarClasses, sizeClasses[size], className);

  if (src) {
    return <img src={src} alt={alt || name} className={avatarClasses} />;
  }

  return (
    <div className={avatarClasses} style={{lineHeight: 1}}>
      {getInitials(name)}
    </div>
  );
}
