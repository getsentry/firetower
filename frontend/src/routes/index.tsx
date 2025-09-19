import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute, Link} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {z} from 'zod';

import {incidentsQueryOptions} from './queries';

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
  loader: ({deps, context}) =>
    context.queryClient.ensureQueryData(incidentsQueryOptions(deps)),
});

function Index() {
  const params = Route.useSearch();
  const {data: incidents} = useSuspenseQuery(incidentsQueryOptions(params));

  return (
    <div className="p-2">
      <h3>Incidents list</h3>
      <ul className="flex flex-col gap-2 list-disc">
        {incidents.map(incident => (
          <li key={incident.id}>
            <h4>
              {incident.id} {incident.title}
            </h4>
            <Link
              to="/$incidentId"
              params={{incidentId: incident.id}}
              className="underline"
              preload={'intent'}
            >
              See incident details
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
