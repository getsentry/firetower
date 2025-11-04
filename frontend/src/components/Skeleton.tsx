import {cn} from 'utils/cn';

interface SkeletonProps {
  className?: string;
}

export const Skeleton = ({className}: SkeletonProps) => {
  return (
    <div
      className={cn('animate-pulse rounded-radius-sm bg-background-secondary', className)}
      aria-hidden="true"
    />
  );
};
