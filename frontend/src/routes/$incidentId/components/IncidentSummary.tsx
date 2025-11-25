import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {Pill} from 'components/Pill';
import {Tag} from 'components/Tag';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {useUpdateIncidentField} from '../queries/incidentMutations';

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

const SEVERITY_OPTIONS = ['P0', 'P1', 'P2', 'P3', 'P4'] as const;
const STATUS_OPTIONS = [
  'Active',
  'Mitigated',
  'Postmortem',
  'Actions Pending',
  'Done',
] as const;

export function IncidentSummary({incident}: IncidentSummaryProps) {
  const updateIncidentField = useUpdateIncidentField();

  const handleSeverityChange = async (newSeverity: (typeof SEVERITY_OPTIONS)[number]) => {
    await updateIncidentField.mutateAsync({
      incidentId: incident.id,
      field: 'severity',
      value: newSeverity,
    });
  };

  const handleStatusChange = async (newStatus: (typeof STATUS_OPTIONS)[number]) => {
    await updateIncidentField.mutateAsync({
      incidentId: incident.id,
      field: 'status',
      value: newStatus,
    });
  };

  return (
    <Card>
      <div className="mb-space-lg flex items-start justify-between">
        <span className="text-content-secondary gap-space-xs flex items-center text-sm leading-none">
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
        <EditablePill
          value={incident.severity}
          options={SEVERITY_OPTIONS}
          onSave={handleSeverityChange}
        />
        <EditablePill
          value={incident.status}
          options={STATUS_OPTIONS}
          onSave={handleStatusChange}
        />
        {incident.is_private && <Pill variant="private">Private</Pill>}
      </div>
      <Card.Title size="2xl">{incident.title}</Card.Title>
      <p className="text-content-secondary leading-comfortable">{incident.description}</p>

      <div className="mt-space-xl grid grid-cols-1 gap-space-xl md:grid-cols-3">
        <div>
          <h3 className="mb-space-md text-size-md font-semibold text-content-secondary">
            Impact
          </h3>
          {incident.impact ? (
            <p className="text-size-sm leading-comfortable text-content-secondary">
              {incident.impact}
            </p>
          ) : (
            <p className="text-size-sm italic text-content-disabled">
              No impact specified
            </p>
          )}
        </div>

        <div>
          <h3 className="mb-space-md text-size-md font-semibold text-content-secondary">
            Affected Areas
          </h3>
          {incident.affected_areas.length > 0 ? (
            <div className="flex flex-wrap gap-space-md">
              {incident.affected_areas.map(area => (
                <Tag key={area}>{area}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-size-sm italic text-content-disabled">
              No affected areas specified
            </p>
          )}
        </div>

        <div>
          <h3 className="mb-space-md text-size-md font-semibold text-content-secondary">
            Root Cause
          </h3>
          {incident.root_causes.length > 0 ? (
            <div className="flex flex-wrap gap-space-md">
              {incident.root_causes.map(cause => (
                <Tag key={cause}>{cause}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-size-sm italic text-content-disabled">
              No root cause specified
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
