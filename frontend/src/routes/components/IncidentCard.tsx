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
      <div className="bg-background-primary rounded-radius-lg p-space-xl shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer">
        <div className="flex flex-wrap items-center gap-space-xl mb-space-md md:flex-nowrap">
          <span className="text-size-md text-content-secondary font-regular">
            {incident.id}
          </span>
          <div className="ml-auto text-size-sm text-content-secondary text-right md:order-last">
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
          <h3 className="w-full text-size-xl font-semibold text-content-headings md:w-auto md:flex-1">
            {incident.title}
          </h3>
        </div>

        <div className="mb-space-lg">
          <div className="flex gap-space-md">
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
