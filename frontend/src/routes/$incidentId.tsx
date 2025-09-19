import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';

import {incidentDetailQueryOptions} from './queries';

export const Route = createFileRoute('/$incidentId')({
  component: Incident,
  loader: ({params, context}) =>
    context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
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
