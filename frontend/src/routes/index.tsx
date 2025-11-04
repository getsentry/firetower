import {useEffect, useRef} from 'react';
import {useSuspenseInfiniteQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {Spinner} from 'components/Spinner';
import {arraysEqual} from 'utils/arrays';
import {z} from 'zod';

import {IncidentCard} from './components/IncidentCard';
import {IncidentListSkeleton} from './components/IncidentListSkeleton';
import {StatusFilter} from './components/StatusFilter';
import {
  incidentsQueryOptions,
  IncidentStatusSchema,
  type IncidentStatus,
} from './queries/incidentsQueryOptions';
import {STATUS_FILTER_GROUPS} from './types';

// Zod schema for search params
const incidentListSearchSchema = z.object({
  status: z.array(IncidentStatusSchema).optional(),
});

function IncidentsLayout({children}: {children: React.ReactNode}) {
  return (
    <div className="flex flex-col">
      <StatusFilter />
      <hr className="mb-space-xl mt-space-lg border-secondary" />
      {children}
    </div>
  );
}

export const Route = createFileRoute('/')({
  // Component to render
  component: Index,
  // Validate search params with zod schema
  validateSearch: zodValidator(incidentListSearchSchema),
  // Extract search params needed for loader
  loaderDeps: ({search: {status}}) => ({status}),
  // Define loader with loaderDeps and context (context has queryClient)
  loader: async ({deps, context}) => {
    const options = incidentsQueryOptions(deps);
    await context.queryClient.prefetchInfiniteQuery(options);
  },
  pendingComponent: () => (
    <IncidentsLayout>
      <IncidentListSkeleton />
    </IncidentsLayout>
  ),
  errorComponent: () => (
    <IncidentsLayout>
      <ErrorState
        title="Something went wrong fetching incidents"
        description={
          <>
            Try refreshing the page, or if that doesn't work, come chat with us in{' '}
            <GetHelpLink />.
          </>
        }
      />
    </IncidentsLayout>
  ),
});

const STORAGE_KEY = 'firetower_list_search';

function IncidentsEmptyState({status}: {status?: IncidentStatus[]}) {
  if (!status || arraysEqual(status, STATUS_FILTER_GROUPS.active)) {
    return (
      <div className="text-content-secondary py-space-4xl text-center">
        <p>There are no active incidents! {String.fromCodePoint(0x1f389)}</p>
      </div>
    );
  }
  if (arraysEqual(status, STATUS_FILTER_GROUPS.review)) {
    return (
      <div className="text-content-secondary py-space-4xl text-center">
        <p>There are no incidents in review.</p>
      </div>
    );
  }
  return (
    <div className="text-content-secondary py-space-4xl text-center">
      <p className="mb-space-lg">There are no incidents matching those filters.</p>
      <p>
        If you think this is a bug, let us know in <GetHelpLink />.
      </p>
    </div>
  );
}

function Index() {
  const params = Route.useSearch();
  const {
    data: incidents,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useSuspenseInfiniteQuery(incidentsQueryOptions(params));

  const observerTarget = useRef<HTMLDivElement>(null);

  // Store current search params in sessionStorage whenever they change
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  }, [params]);

  // Infinite scroll observer
  useEffect(() => {
    const target = observerTarget.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      {threshold: 0.1}
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  return (
    <IncidentsLayout>
      {incidents.length === 0 ? (
        <IncidentsEmptyState status={params.status} />
      ) : (
        <>
          <ul className="gap-space-lg flex list-none flex-col">
            {incidents.map(incident => (
              <li key={incident.id}>
                <IncidentCard incident={incident} />
              </li>
            ))}
          </ul>

          {/* Intersection observer target */}
          <div ref={observerTarget} className="py-space-xl flex justify-center">
            {isFetchingNextPage && <Spinner size="md" />}
          </div>
        </>
      )}
    </IncidentsLayout>
  );
}
