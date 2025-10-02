import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';

import {Card} from '../components/Card';
import {Pill} from '../components/Pill';

import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId')({
  component: Incident,
  loader: async ({params, context}) =>
    await context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
  pendingComponent: () => <p>Loading incident...</p>,
  errorComponent: () => <p>Something went wrong fetching incident.</p>,
});

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  const dateFormatted = date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  const timeFormatted = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
  return `${dateFormatted} • ${timeFormatted}`;
}

function Incident() {
  const params = Route.useParams();
  const {data: incident} = useSuspenseQuery(incidentDetailQueryOptions(params));

  return (
    <div className="p-2">
      <Card>
        <div className="flex justify-between items-start mb-space-lg">
          <div className="text-sm text-content-secondary">{incident.id}</div>
          <div className="text-sm text-content-secondary text-right">
            {formatDateTime(incident.created_at)}
          </div>
        </div>
        <div className="flex gap-space-lg mb-space-xl">
          <Pill variant={incident.severity}>{incident.severity}</Pill>
          {incident.is_private && <Pill variant="private">Private</Pill>}
          <Pill variant={incident.status}>{incident.status}</Pill>
        </div>
        <Card.Title size="2xl">{incident.title}</Card.Title>
        <p className="text-content-secondary leading-comfortable">
          {incident.description}
        </p>
      </Card>
    </div>
  );
}
