import {Link} from '@tanstack/react-router';

import {Pill} from '../../components/Pill';
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
      <div className="bg-background-primary rounded-radius-lg p-space-xl cursor-pointer shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
        <div className="gap-space-xl mb-space-md flex flex-wrap items-center md:flex-nowrap">
          <span className="text-size-md text-content-secondary font-regular">
            {incident.id}
          </span>
          <div className="text-size-sm text-content-secondary ml-auto text-right md:order-last">
            <div>
              {createdAt.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </div>
            <div>
              Opened{' '}
              {createdAt.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
              })}
            </div>
          </div>
          <h3 className="text-size-xl text-content-headings w-full font-semibold md:w-auto md:flex-1">
            {incident.title}
          </h3>
        </div>

        <div className="mb-space-lg">
          <div className="gap-space-md flex">
            <Pill variant={incident.severity}>{incident.severity}</Pill>
            <Pill variant={incident.status}>{incident.status}</Pill>
            {incident.is_private && <Pill variant="private">Private</Pill>}
          </div>
        </div>

        <p className="text-content-secondary text-size-sm leading-comfortable">
          {incident.description}
        </p>
      </div>
    </Link>
  );
};
