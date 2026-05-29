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
        <div className="gap-space-xl mb-space-md flex flex-wrap items-center md:flex-nowrap">
          <span className="text-size-lg text-content-secondary gap-space-xs flex select-text items-center font-regular leading-none">
            {incident.is_private && <span aria-label="Private incident">🔒</span>}
            {incident.id}
          </span>
          <div className="text-size-sm text-content-secondary ml-auto select-none text-right md:order-last">
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
          </div>
          <h3 className="text-size-xl text-content-headings w-full select-text font-semibold md:w-auto md:flex-1">
            {incident.title}
          </h3>
        </div>

        <div className="mb-space-lg flex items-center justify-between">
          <div className="gap-space-md flex">
            <Pill variant={incident.severity}>{incident.severity}</Pill>
            <Pill variant={incident.status}>{incident.status}</Pill>
            {incident.is_private && <Pill variant="private">Private</Pill>}
          </div>
          {incident.captain && (
            <p className="text-content-secondary text-size-sm select-none">
              Captain: {incident.captain}
            </p>
          )}
        </div>

        {incident.description ? (
          <p className="text-content-secondary text-size-sm leading-comfortable line-clamp-1 select-none">
            {incident.description}
          </p>
        ) : null}
      </div>
    </Link>
  );
};
