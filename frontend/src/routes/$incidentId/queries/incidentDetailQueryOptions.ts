import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const ParticipantSchema = z.object({
  name: z.string(),
  avatar_url: z.string().nullable(),
  role: z.string(),
});

const ExternalLinksSchema = z.object({
  slack: z.string().optional(),
  jira: z.string().optional(),
  datadog: z.string().optional(),
  pagerduty: z.string().optional(),
  statuspage: z.string().optional(),
  notion: z.string().optional(),
  linear: z.string().optional(),
});

const IncidentDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  impact: z.string(),
  status: z.enum(['Active', 'Mitigated', 'Postmortem', 'Actions Pending', 'Done']),
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  created_at: z.string(),
  updated_at: z.string(),
  is_private: z.boolean(),
  affected_areas: z.array(z.string()),
  root_causes: z.array(z.string()),
  participants: z.array(ParticipantSchema),
  external_links: ExternalLinksSchema,
});

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
        responseSchema: IncidentDetailSchema,
      }),
  });
}
