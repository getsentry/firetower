import {Skeleton} from 'components/Skeleton';

export const IncidentDetailSkeleton = () => {
  return (
    <div className="space-y-4 p-2">
      <Skeleton className="rounded-radius-lg h-48 w-full shadow-sm" />
      <div className="flex flex-col gap-4 md:flex-row">
        <div className="md:flex-[2]">
          <Skeleton className="rounded-radius-lg h-64 w-full shadow-sm" />
        </div>
        <aside className="flex flex-col gap-4 md:flex-1">
          <Skeleton className="rounded-radius-lg h-32 w-full shadow-sm" />
          <Skeleton className="rounded-radius-lg h-40 w-full shadow-sm" />
          <Skeleton className="rounded-radius-lg h-48 w-full shadow-sm" />
        </aside>
      </div>
    </div>
  );
};
