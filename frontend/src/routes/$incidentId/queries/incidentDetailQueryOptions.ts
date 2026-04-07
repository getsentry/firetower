import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import {ServiceTierSchema, SeveritySchema, StatusSchema} from '../../types';

const ParticipantSchema = z.object({
  name: z.string(),
  avatar_url: z.string().nullable(),
  role: z.enum(['Captain', 'Reporter', 'Participant']),
  email: z.string(),
});

const ExternalLinksSchema = z.object({
  slack: z.string().optional(),
  jira: z.string().optional(),
  datadog: z.string().optional(),
  pagerduty: z.string().optional(),
  statuspage: z.string().optional(),
  notion: z.string().optional(),
  notion_troubleshooting: z.string().optional(),
  linear: z.string().optional(),
});

const ActionItemStatusSchema = z.enum(['Todo', 'In Progress', 'Done', 'Cancelled']);

const ActionItemSchema = z.object({
  linear_identifier: z.string(),
  title: z.string(),
  status: ActionItemStatusSchema,
  assignee_name: z.string().nullable(),
  assignee_avatar_url: z.string().nullable(),
  url: z.string(),
});

export type ActionItem = z.infer<typeof ActionItemSchema>;
export type ActionItemStatus = z.infer<typeof ActionItemStatusSchema>;

const IncidentDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  impact_summary: z.string(),
  status: StatusSchema,
  severity: SeveritySchema,
  service_tier: ServiceTierSchema.nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  is_private: z.boolean(),
  affected_service_tags: z.array(z.string()),
  affected_region_tags: z.array(z.string()),
  root_cause_tags: z.array(z.string()),
  impact_type_tags: z.array(z.string()),
  participants: z.array(ParticipantSchema),
  external_links: ExternalLinksSchema,
  action_items: z.array(ActionItemSchema),
  time_started: z.string().nullable(),
  time_detected: z.string().nullable(),
  time_analyzed: z.string().nullable(),
  time_mitigated: z.string().nullable(),
  time_recovered: z.string().nullable(),
  total_downtime: z.number().int().nullable(),
});

const IncidentOrRedirectSchema = z.union([
  z.object({incident: IncidentDetailSchema}),
  z.object({redirect: z.url()}),
]);

export type IncidentDetail = z.infer<typeof IncidentDetailSchema>;
export {IncidentDetailSchema};

interface IncidentDetailQueryArgs {
  incidentId: string;
}

export function incidentDetailQueryOptions({incidentId}: IncidentDetailQueryArgs) {
  return queryOptions({
    queryKey: ['IncidentDetail', incidentId],
    queryFn: ({signal}) =>
      Api.get({
        path: `/ui/incidents/${incidentId}/`,
        signal,
        responseSchema: IncidentOrRedirectSchema,
      }),
  });
}
