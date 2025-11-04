import {cn} from 'utils/cn';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export const Skeleton = ({className, style}: SkeletonProps) => {
  return (
    <div
      className={cn('animate-pulse rounded-radius-sm bg-background-secondary', className)}
      style={style}
      aria-hidden="true"
    />
  );
};
