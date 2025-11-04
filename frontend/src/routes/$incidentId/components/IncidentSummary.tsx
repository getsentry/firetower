import {Card} from 'components/Card';
import {Pill} from 'components/Pill';
import {Tag} from 'components/Tag';

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
        <span className="text-content-secondary text-sm flex items-center gap-space-xs leading-none">
          {incident.is_private && <span aria-label="Private incident">🔒</span>}
          {incident.id}
        </span>
        <time
          className="text-content-secondary text-right text-sm"
          dateTime={incident.created_at}
        >
          {formatDateTime(incident.created_at)}
        </time>
      </div>
      <div className="gap-space-lg mb-space-xl flex">
        <Pill variant={incident.severity}>{incident.severity}</Pill>
        <Pill variant={incident.status}>{incident.status}</Pill>
        {incident.is_private && <Pill variant="private">Private</Pill>}
      </div>
      <Card.Title size="2xl">{incident.title}</Card.Title>
      <p className="text-content-secondary leading-comfortable">{incident.description}</p>

      <div className="mt-space-xl grid grid-cols-1 gap-space-xl md:grid-cols-3">
        <div>
          <h3 className="text-size-md font-semibold text-content-secondary mb-space-md">
            Impact
          </h3>
          {incident.impact ? (
            <p className="text-content-secondary text-size-sm leading-comfortable">
              {incident.impact}
            </p>
          ) : (
            <p className="text-content-disabled text-size-sm italic">
              No impact specified
            </p>
          )}
        </div>

        <div>
          <h3 className="text-size-md font-semibold text-content-secondary mb-space-md">
            Affected Areas
          </h3>
          {incident.affected_areas.length > 0 ? (
            <div className="flex flex-wrap gap-space-md">
              {incident.affected_areas.map(area => (
                <Tag key={area}>{area}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-content-disabled text-size-sm italic">
              No affected areas specified
            </p>
          )}
        </div>

        <div>
          <h3 className="text-size-md font-semibold text-content-secondary mb-space-md">
            Root Cause
          </h3>
          {incident.root_causes.length > 0 ? (
            <div className="flex flex-wrap gap-space-md">
              {incident.root_causes.map(cause => (
                <Tag key={cause}>{cause}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-content-disabled text-size-sm italic">
              No root cause specified
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
