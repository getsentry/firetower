import {useEffect, useRef} from 'react';
import {useSuspenseInfiniteQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Spinner} from 'components/Spinner';
import {z} from 'zod';

import {IncidentCard} from './components/IncidentCard';
import {StatusFilter} from './components/StatusFilter';
import {
  incidentsQueryOptions,
  IncidentStatusSchema,
} from './queries/incidentsQueryOptions';

// Zod schema for search params
const incidentListSearchSchema = z.object({
  status: z.array(IncidentStatusSchema).optional().default(['Active', 'Mitigated']),
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
      <div className="py-space-4xl flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    </IncidentsLayout>
  ),
  errorComponent: () => (
    <IncidentsLayout>
      <p className="text-content-secondary py-space-4xl text-center">
        Something went wrong fetching incidents.
      </p>
    </IncidentsLayout>
  ),
  notFoundComponent: () => (
    <IncidentsLayout>
      <p className="text-content-secondary py-space-4xl text-center">Page not found.</p>
    </IncidentsLayout>
  ),
});

const STORAGE_KEY = 'firetower_list_search';

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
    </IncidentsLayout>
  );
}
