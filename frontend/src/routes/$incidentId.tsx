import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';

import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId')({
  component: Incident,
  loader: async ({params, context}) =>
    await context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
  pendingComponent: () => <p>Loading incident...</p>,
  errorComponent: () => <p>Something went wrong fetching incident.</p>,
});

function Incident() {
  const params = Route.useParams();
  const {data: incident} = useSuspenseQuery(incidentDetailQueryOptions(params));

  return (
    <div className="p-2">
      <h3>
        {incident.id}: {incident.title}
      </h3>
      <div>Status: {incident.status}</div>
      <div>Severity: {incident.severity}</div>
      <p>{incident.description}</p>
    </div>
  );
}
