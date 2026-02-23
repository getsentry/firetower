import {Link} from '@tanstack/react-router';

import type {RegionAvailability} from '../queries/availabilityQueryOptions';

function formatAvailability(pct: number): string {
  if (pct >= 100) return '100%';
  return pct.toFixed(2) + '%';
}

interface AvailabilityCellProps {
  data: RegionAvailability;
  showIncidents: boolean;
}

export function AvailabilityCell({data, showIncidents}: AvailabilityCellProps) {
  const pct = data.availability_percentage;
  return (
    <div className="space-y-0.5">
      <div className="text-lg tabular-nums text-content-headings">
        {formatAvailability(pct)}
      </div>
      <div className="text-xs text-content-secondary tabular-nums">
        {data.total_downtime_display ? data.total_downtime_display : '—'}
        {data.incident_count > 0 && (
          <>
            {' '}
            · {data.incident_count} {data.incident_count === 1 ? 'incident' : 'incidents'}
          </>
        )}
      </div>
      {showIncidents && data.incidents.length > 0 && (
        <div className="mt-space-xs space-y-0.5 border-t border-secondary pt-1">
          {data.incidents.map(incident => (
            <div
              key={incident.id}
              title={`INC-${incident.id} · ${incident.title} · ${incident.total_downtime_display ? incident.total_downtime_display : '—'}`}
              className="flex items-baseline gap-space-xs"
            >
              <Link
                to="/$incidentId"
                params={{incidentId: `INC-${incident.id}`}}
                className="text-xs text-content-accent hover:underline font-medium shrink-0"
              >
                INC-{incident.id}
              </Link>
              <span className="text-xs text-content-secondary tabular-nums shrink-0 ml-auto">
                {incident.total_downtime_display ? incident.total_downtime_display : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
