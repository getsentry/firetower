import {Card} from 'components/Card';
import {Pill} from 'components/Pill';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

interface IncidentSummaryProps {
  incident: IncidentDetail;
}

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

export function IncidentSummary({incident}: IncidentSummaryProps) {
  return (
    <Card>
      <div className="mb-space-lg flex items-start justify-between">
        <span className="text-content-secondary text-sm">{incident.id}</span>
        <time
          className="text-content-secondary text-right text-sm"
          dateTime={incident.created_at}
        >
          {formatDateTime(incident.created_at)}
        </time>
      </div>
      <div className="gap-space-lg mb-space-xl flex">
        <Pill variant={incident.severity}>{incident.severity}</Pill>
        {incident.is_private && <Pill variant="private">Private</Pill>}
        <Pill variant={incident.status}>{incident.status}</Pill>
      </div>
      <Card.Title size="2xl">{incident.title}</Card.Title>
      <p className="text-content-secondary leading-comfortable">{incident.description}</p>
    </Card>
  );
}
