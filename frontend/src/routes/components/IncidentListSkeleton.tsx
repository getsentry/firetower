import {Skeleton} from 'components/Skeleton';

export const IncidentListSkeleton = () => {
  return (
    <div className="gap-space-lg flex flex-col">
      <Skeleton
        className="h-32 w-full rounded-radius-lg shadow-sm"
        style={{animationDelay: '0ms'}}
      />
      <Skeleton
        className="h-32 w-full rounded-radius-lg shadow-sm"
        style={{animationDelay: '400ms'}}
      />
      <Skeleton
        className="h-32 w-full rounded-radius-lg shadow-sm"
        style={{animationDelay: '800ms'}}
      />
      <Skeleton
        className="h-32 w-full rounded-radius-lg shadow-sm"
        style={{animationDelay: '1200ms'}}
      />
      <Skeleton
        className="h-32 w-full rounded-radius-lg shadow-sm"
        style={{animationDelay: '1600ms'}}
      />
    </div>
  );
};
