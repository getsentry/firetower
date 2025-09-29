import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute, Link} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {z} from 'zod';

import {Card} from '../components/Card';
import {Pill} from '../components/Pill';

import {incidentsQueryOptions} from './queries/incidentsQueryOptions';

// Zod schema for search params
const incidentListSearchSchema = z.object({
  status: z.string().optional(),
});

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
  pendingComponent: () => <p>Loading incidents...</p>,
  errorComponent: () => <p>Something went wrong fetching incidents.</p>,
});

function Index() {
  const params = Route.useSearch();
  const {data: incidents} = useSuspenseQuery(incidentsQueryOptions(params));

  return (
    <div className="flex flex-col gap-space-lg">
      {incidents.map(incident => (
        <Card key={incident.id}>
          <Card.Title>
            {incident.id} {incident.title}
          </Card.Title>
          <Pill variant={incident.severity}>{incident.severity}</Pill>
          <Link
            to="/$incidentId"
            params={{incidentId: incident.id}}
            className="underline"
            preload={'intent'}
          >
            link
          </Link>
        </Card>
      ))}
    </div>
  );
}
