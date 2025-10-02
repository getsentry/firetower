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
      <p className="text-content-secondary leading-comfortable">{incident.description}</p>
    </Card>
  );
}
