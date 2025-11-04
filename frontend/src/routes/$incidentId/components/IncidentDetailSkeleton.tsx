import {Skeleton} from 'components/Skeleton';

export const IncidentDetailSkeleton = () => {
  return (
    <div className="space-y-4 p-2">
      <Skeleton className="h-48 w-full rounded-radius-lg shadow-sm" />
      <div className="flex flex-col gap-4 md:flex-row">
        <div className="md:flex-[2]">
          <Skeleton className="h-64 w-full rounded-radius-lg shadow-sm" />
        </div>
        <aside className="flex flex-col gap-4 md:flex-1">
          <Skeleton className="h-32 w-full rounded-radius-lg shadow-sm" />
          <Skeleton className="h-40 w-full rounded-radius-lg shadow-sm" />
          <Skeleton className="h-48 w-full rounded-radius-lg shadow-sm" />
        </aside>
      </div>
    </div>
  );
};
