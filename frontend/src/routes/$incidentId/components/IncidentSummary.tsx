import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {Pill} from 'components/Pill';
import {Tag} from 'components/Tag';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {SEVERITY_OPTIONS, STATUS_OPTIONS} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

import {OverflowMenu} from './OverflowMenu';

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
  const queryClient = useQueryClient();
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

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

  const handleVisibilityToggle = async () => {
    await updateIncidentField.mutateAsync({
      incidentId: incident.id,
      field: 'is_private',
      value: !incident.is_private,
    });
  };

  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <span className="text-content-secondary gap-space-xs flex items-center text-sm leading-none">
          {incident.is_private && <span aria-label="Private incident">🔒</span>}
          {incident.id}
        </span>
        <div className="gap-space-md flex items-center">
          <time
            className="text-content-secondary text-right text-sm"
            dateTime={incident.created_at}
          >
            {formatDateTime(incident.created_at)}
          </time>
          <OverflowMenu
            isPrivate={incident.is_private}
            onToggleVisibility={handleVisibilityToggle}
          />
        </div>
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

      <div className="mt-space-xl gap-space-xl grid grid-cols-1 md:grid-cols-3">
        <div>
          <h3 className="mb-space-md text-size-md text-content-secondary font-semibold">
            Impact
          </h3>
          {incident.impact ? (
            <p className="text-size-sm leading-comfortable text-content-secondary">
              {incident.impact}
            </p>
          ) : (
            <p className="text-size-sm text-content-disabled italic">
              No impact specified
            </p>
          )}
        </div>

        <div>
          <h3 className="mb-space-md text-size-md text-content-secondary font-semibold">
            Affected Areas
          </h3>
          {incident.affected_areas.length > 0 ? (
            <div className="gap-space-md flex flex-wrap">
              {incident.affected_areas.map(area => (
                <Tag key={area}>{area}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-size-sm text-content-disabled italic">
              No affected areas specified
            </p>
          )}
        </div>

        <div>
          <h3 className="mb-space-md text-size-md text-content-secondary font-semibold">
            Root Cause
          </h3>
          {incident.root_causes.length > 0 ? (
            <div className="gap-space-md flex flex-wrap">
              {incident.root_causes.map(cause => (
                <Tag key={cause}>{cause}</Tag>
              ))}
            </div>
          ) : (
            <p className="text-size-sm text-content-disabled italic">
              No root cause specified
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
