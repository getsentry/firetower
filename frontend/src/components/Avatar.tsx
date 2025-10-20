import {cn} from 'utils/cn';

const avatarClasses = [
  'bg-background-tertiary',
  'text-content-secondary',
  'flex',
  'h-10',
  'w-10',
  'items-center',
  'justify-center',
  'rounded-full',
  'text-base',
  'font-semibold',
  'shrink-0',
].join(' ');

export interface AvatarProps {
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

export function Avatar({name, src, alt, className}: AvatarProps) {
  if (src) {
    return <img src={src} alt={alt || name} className={cn(avatarClasses, className)} />;
  }

  return (
    <div className={cn(avatarClasses, className)} style={{lineHeight: 1}}>
      {getInitials(name)}
    </div>
  );
}
