import * as stylex from '@stylexjs/stylex';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {EditableTags} from 'components/EditableTags';
import {EditableTextField} from 'components/EditableTextField';
import {Pill} from 'components/Pill';

import {content, fontSize, space} from '../../../styles/tokens.stylex';
import {ServiceTierSchema, SeveritySchema, StatusSchema} from '../../types';
import {createTagMutationOptions} from '../queries/createTagMutationOptions';
import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
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
  const createTag = useMutation(createTagMutationOptions(queryClient));

  const {data: affectedServiceSuggestions = []} = useQuery(
    tagsQueryOptions('AFFECTED_SERVICE')
  );
  const {data: affectedRegionSuggestions = []} = useQuery(
    tagsQueryOptions('AFFECTED_REGION')
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
      <div {...stylex.props(styles.header)}>
        <span {...stylex.props(styles.identifier)}>
          {incident.is_private && <span aria-label="Private incident">🔒</span>}
          {incident.id}
        </span>
        <div {...stylex.props(styles.metadata)}>
          <time {...stylex.props(styles.createdAt)} dateTime={incident.created_at}>
            {formatDateTime(incident.created_at)}
          </time>
          <OverflowMenu
            isPrivate={incident.is_private}
            onToggleVisibility={handleVisibilityToggle}
          />
        </div>
      </div>
      <div {...stylex.props(styles.pills)}>
        <EditablePill
          value={incident.severity}
          options={SeveritySchema.options}
          onSave={handleFieldChange('severity')}
        />
        <EditablePill
          value={incident.status}
          options={StatusSchema.options}
          onSave={handleFieldChange('status')}
        />
        <EditablePill
          value={incident.service_tier}
          options={ServiceTierSchema.options}
          onSave={handleFieldChange('service_tier')}
          placeholder="Service tier"
        />
        {incident.is_private && <Pill variant="private">Private</Pill>}
      </div>
      <div {...stylex.props(styles.titleContainer)}>
        <EditableTextField
          value={incident.title}
          onSave={handleFieldChange('title')}
          as="h3"
          style={styles.title}
        />
      </div>
      <EditableTextField
        value={incident.description}
        onSave={handleFieldChange('description')}
        as="p"
        multiline
        placeholder="No description provided"
        style={styles.secondary}
        label="Description"
        labelStyle={styles.label}
      />

      <div {...stylex.props(styles.details)}>
        <div>
          <EditableTextField
            value={incident.impact_summary}
            onSave={handleFieldChange('impact_summary')}
            label="Impact summary"
            labelStyle={styles.label}
            as="p"
            multiline
            placeholder="No impact specified"
            style={styles.impactSummary}
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
          label="Affected services"
          tags={incident.affected_service_tags}
          onSave={async newTags => {
            await updateIncidentField.mutateAsync({
              incidentId: incident.id,
              field: 'affected_service_tags',
              value: newTags,
            });
          }}
          suggestions={affectedServiceSuggestions}
          emptyText="No affected services specified"
          allowTagCreation
          onCreateTag={async name => {
            await createTag.mutateAsync({name, type: 'AFFECTED_SERVICE'});
          }}
        />

        <EditableTags
          label="Affected regions"
          tags={incident.affected_region_tags}
          onSave={async newTags => {
            await updateIncidentField.mutateAsync({
              incidentId: incident.id,
              field: 'affected_region_tags',
              value: newTags,
            });
          }}
          suggestions={affectedRegionSuggestions}
          emptyText="No affected regions specified"
          allowTagCreation
          onCreateTag={async name => {
            await createTag.mutateAsync({name, type: 'AFFECTED_REGION'});
          }}
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
          allowTagCreation
          onCreateTag={async name => {
            await createTag.mutateAsync({name, type: 'ROOT_CAUSE'});
          }}
        />
      </div>
    </Card>
  );
}

const styles = stylex.create({
  header: {
    marginBottom: space.lg,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  identifier: {
    color: content.secondary,
    gap: space.xs,
    display: 'flex',
    alignItems: 'center',
    fontSize: '14px',
    lineHeight: 1,
  },
  metadata: {gap: space.md, display: 'flex', alignItems: 'center'},
  createdAt: {
    color: content.secondary,
    textAlign: 'right',
    fontSize: '14px',
    lineHeight: '20px',
  },
  pills: {gap: space.lg, marginBottom: space.xl, display: 'flex'},
  titleContainer: {marginBottom: space.xl},
  title: {color: content.headings, fontSize: '24px', lineHeight: '32px', fontWeight: 600},
  secondary: {color: content.secondary},
  label: {fontSize: fontSize.md, fontWeight: 600},
  details: {
    marginTop: space.xl,
    gap: space.xl,
    display: 'grid',
    gridTemplateColumns: {
      default: 'repeat(1, minmax(0, 1fr))',
      '@media (min-width: 768px)': 'repeat(2, minmax(0, 1fr))',
      '@media (min-width: 1024px)': 'repeat(5, minmax(0, 1fr))',
    },
  },
  impactSummary: {fontSize: fontSize.sm, color: content.secondary},
});
