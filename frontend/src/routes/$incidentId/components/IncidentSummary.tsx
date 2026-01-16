import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {EditableTags} from 'components/EditableTags';
import {EditableTextField} from 'components/EditableTextField';
import {Pill} from 'components/Pill';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {
  SERVICE_TIER_OPTIONS,
  SEVERITY_OPTIONS,
  STATUS_OPTIONS,
} from '../queries/incidentDetailQueryOptions';
import {tagsQueryOptions} from '../queries/tagsQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

import {OverflowMenu} from './OverflowMenu';

interface IncidentSummaryProps {
  incident: IncidentDetail;
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });
}

export function IncidentSummary({incident}: IncidentSummaryProps) {
  const queryClient = useQueryClient();
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

  const {data: affectedAreaSuggestions = []} = useQuery(
    tagsQueryOptions('AFFECTED_AREA')
  );
  const {data: rootCauseSuggestions = []} = useQuery(tagsQueryOptions('ROOT_CAUSE'));
  const {data: impactTypeSuggestions = []} = useQuery(tagsQueryOptions('IMPACT_TYPE'));

  const handleFieldChange =
    (
      field:
        | 'severity'
        | 'status'
        | 'service_tier'
        | 'title'
        | 'description'
        | 'impact_summary'
    ) =>
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
        <EditablePill
          value={incident.service_tier}
          options={SERVICE_TIER_OPTIONS}
          onSave={handleFieldChange('service_tier')}
          placeholder="Service tier"
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
        className="text-content-secondary"
        label="Description"
        labelClassName="text-size-md font-semibold"
      />

      <div className="mt-space-xl gap-space-xl grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
        <div>
          <EditableTextField
            value={incident.impact_summary}
            onSave={handleFieldChange('impact_summary')}
            label="Impact summary"
            labelClassName="text-size-md font-semibold"
            as="p"
            multiline
            placeholder="No impact specified"
            className="text-size-sm text-content-secondary"
          />
        </div>

        <EditableTags
          label="Impact type"
          tags={incident.impact_type_tags}
          onSave={async newTags => {
            await updateIncidentField.mutateAsync({
              incidentId: incident.id,
              field: 'impact_type_tags',
              value: newTags,
            });
          }}
          suggestions={impactTypeSuggestions}
          emptyText="No impact type specified"
        />

        <EditableTags
          label="Affected areas"
          tags={incident.affected_area_tags}
          onSave={async newTags => {
            await updateIncidentField.mutateAsync({
              incidentId: incident.id,
              field: 'affected_area_tags',
              value: newTags,
            });
          }}
          suggestions={affectedAreaSuggestions}
          emptyText="No affected areas specified"
        />

        <EditableTags
          label="Root cause"
          tags={incident.root_cause_tags}
          onSave={async newTags => {
            await updateIncidentField.mutateAsync({
              incidentId: incident.id,
              field: 'root_cause_tags',
              value: newTags,
            });
          }}
          suggestions={rootCauseSuggestions}
          emptyText="No root cause specified"
        />
      </div>
    </Card>
  );
}
