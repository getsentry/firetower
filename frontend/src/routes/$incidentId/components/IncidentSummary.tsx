import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {EditableTextField} from 'components/EditableTextField';
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

  const handleFieldChange =
    (field: 'severity' | 'status' | 'title' | 'description' | 'impact') =>
    async (value: string) => {
      await updateIncidentField.mutateAsync({
        incidentId: incident.id,
        field,
        value,
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
          onSave={handleFieldChange('severity')}
        />
        <EditablePill
          value={incident.status}
          options={STATUS_OPTIONS}
          onSave={handleFieldChange('status')}
        />
        {incident.is_private && <Pill variant="private">Private</Pill>}
      </div>
      <div className="mb-space-xl">
        <EditableTextField
          value={incident.title}
          onSave={handleFieldChange('title')}
          as="h3"
          className="text-content-headings text-2xl font-semibold"
        />
      </div>
      <EditableTextField
        value={incident.description}
        onSave={handleFieldChange('description')}
        as="p"
        multiline
        placeholder="No description provided"
        className="text-content-secondary leading-comfortable"
      />

      <div className="mt-space-xl gap-space-xl grid grid-cols-1 md:grid-cols-3">
        <div>
          <EditableTextField
            value={incident.impact}
            onSave={handleFieldChange('impact')}
            label="Impact"
            labelClassName="text-size-md font-semibold"
            as="p"
            multiline
            placeholder="No impact provided"
            className="text-size-sm leading-comfortable text-content-secondary"
          />
        </div>

        <div>
          <h3 className="mb-space-md text-size-md text-content-secondary font-semibold">
            Affected Areas
          </h3>
          {incident.affected_area_tags.length > 0 ? (
            <div className="gap-space-md flex flex-wrap">
              {incident.affected_area_tags.map(area => (
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
          {incident.root_cause_tags.length > 0 ? (
            <div className="gap-space-md flex flex-wrap">
              {incident.root_cause_tags.map(cause => (
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
