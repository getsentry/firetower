import {useEffect} from 'react';
import {useSuspenseQuery} from '@tanstack/react-query';
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
  loader: async ({deps, context}) =>
    await context.queryClient.ensureQueryData(incidentsQueryOptions(deps)),
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
  const {data: paginatedIncidents} = useSuspenseQuery(incidentsQueryOptions(params));

  // Store current search params in sessionStorage whenever they change
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  }, [params]);

  return (
    <IncidentsLayout>
      <ul className="gap-space-lg flex list-none flex-col">
        {paginatedIncidents.results.map(incident => (
          <li key={incident.id}>
            <IncidentCard incident={incident} />
          </li>
        ))}
      </ul>
    </IncidentsLayout>
  );
}
