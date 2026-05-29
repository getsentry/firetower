import {Link} from '@tanstack/react-router';
import {Pill} from 'components/Pill';

import type {IncidentListItem} from '../queries/incidentsQueryOptions';

interface IncidentCardProps {
  incident: IncidentListItem;
}

export const IncidentCard = ({incident}: IncidentCardProps) => {
  const createdAt = new Date(incident.created_at);

  return (
    <Link
      to="/$incidentId"
      params={{incidentId: incident.id}}
      className="block no-underline"
      preload={'intent'}
    >
      <div
        className="bg-background-primary hover:bg-background-transparent-neutral-muted rounded-radius-lg p-space-xl cursor-pointer shadow-sm transition-colors duration-200"
        data-testid={`incident-card-${incident.id}`}
      >
        <div className="gap-space-xl flex justify-between">
          <div className="min-w-0 flex-1">
            <span className="text-size-lg text-content-secondary mb-space-sm gap-space-xs flex select-text items-center font-regular leading-none">
              {incident.is_private && <span aria-label="Private incident">🔒</span>}
              {incident.id}
            </span>
            <h3 className="text-size-xl text-content-headings select-text font-semibold">
              {incident.title}
            </h3>
            <div className="gap-space-md mt-space-md flex">
              <Pill variant={incident.severity}>{incident.severity}</Pill>
              <Pill variant={incident.status}>{incident.status}</Pill>
              {incident.is_private && <Pill variant="private">Private</Pill>}
            </div>
            {incident.description ? (
              <p className="text-content-secondary text-size-sm leading-comfortable line-clamp-1 mt-space-md select-none">
                {incident.description}
              </p>
            ) : null}
          </div>
          <div className="text-size-sm text-content-secondary shrink-0 select-none text-right">
            <time dateTime={incident.created_at}>
              {createdAt.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </time>
            <p>
              Opened{' '}
              {createdAt.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
                timeZoneName: 'short',
              })}
            </p>
            {incident.captain && (
              <p className="mt-space-xs">Captain: {incident.captain}</p>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
};
