import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {z} from 'zod';

import {Spinner} from '../components/Spinner';

import {IncidentCard} from './components/IncidentCard';
import {StatusFilter} from './components/StatusFilter';
import {incidentsQueryOptions} from './queries/incidentsQueryOptions';

// Zod schema for search params
const incidentListSearchSchema = z.object({
  status: z
    .array(z.enum(['Active', 'Mitigated', 'Postmortem', 'Actions Pending', 'Done']))
    .optional()
    .default(['Active', 'Mitigated']),
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
      <div className="flex items-center justify-center py-space-4xl">
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

function Index() {
  const params = Route.useSearch();
  const {data: incidents} = useSuspenseQuery(incidentsQueryOptions(params));

  return (
    <IncidentsLayout>
      <div className="gap-space-lg flex flex-col">
        {incidents.map(incident => (
          <IncidentCard key={incident.id} incident={incident} />
        ))}
      </div>
    </IncidentsLayout>
  );
}
