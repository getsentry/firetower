import {Skeleton} from 'components/Skeleton';

export const IncidentListSkeleton = () => {
  return (
    <div className="gap-space-lg flex flex-col">
      <Skeleton
        className="rounded-radius-lg h-32 w-full shadow-sm"
        style={{animationDelay: '0ms'}}
      />
      <Skeleton
        className="rounded-radius-lg h-32 w-full shadow-sm"
        style={{animationDelay: '400ms'}}
      />
      <Skeleton
        className="rounded-radius-lg h-32 w-full shadow-sm"
        style={{animationDelay: '800ms'}}
      />
      <Skeleton
        className="rounded-radius-lg h-32 w-full shadow-sm"
        style={{animationDelay: '1200ms'}}
      />
      <Skeleton
        className="rounded-radius-lg h-32 w-full shadow-sm"
        style={{animationDelay: '1600ms'}}
      />
    </div>
  );
};
