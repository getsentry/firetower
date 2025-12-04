import {useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {EditableTags} from 'components/EditableTags';
import {EditableTextField} from 'components/EditableTextField';
import {Pill} from 'components/Pill';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {SEVERITY_OPTIONS, STATUS_OPTIONS} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

import {OverflowMenu} from './OverflowMenu';

const AREA_SUGGESTIONS = [
  'API',
  'Database',
  'Frontend',
  'Backend',
  'Authentication',
  'Payments',
  'Notifications',
  'Search',
  'CDN',
  'Cache',
];

const ROOT_CAUSE_SUGGESTIONS = [
  'Configuration error',
  'Code bug',
  'Infrastructure failure',
  'Dependency issue',
  'Resource exhaustion',
  'Network issue',
  'Human error',
  'Security incident',
];

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

  // Local state for tags (wireframe only - no API calls)
  const [affectedAreas, setAffectedAreas] = useState(incident.affected_areas);
  const [rootCauses, setRootCauses] = useState(incident.root_causes);

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
            className="text-size-sm leading-comfortable text-content-secondary"
          />
        </div>

        <EditableTags
          label="Affected Areas"
          tags={affectedAreas}
          onSave={async newTags => {
            setAffectedAreas(newTags);
          }}
          suggestions={AREA_SUGGESTIONS}
          emptyText="No affected areas specified"
        />

        <EditableTags
          label="Root Cause"
          tags={rootCauses}
          onSave={async newTags => {
            setRootCauses(newTags);
          }}
          suggestions={ROOT_CAUSE_SUGGESTIONS}
          emptyText="No root cause specified"
        />
      </div>
    </Card>
  );
}
