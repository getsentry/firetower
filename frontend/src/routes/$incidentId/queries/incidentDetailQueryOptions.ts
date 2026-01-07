import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

export const SEVERITY_OPTIONS = ['P0', 'P1', 'P2', 'P3', 'P4'] as const;
export const SERVICE_TIER_OPTIONS = ['T0', 'T1', 'T2', 'T3', 'T4'] as const;
export const STATUS_OPTIONS = ['Active', 'Mitigated', 'Postmortem', 'Done'] as const;

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
  linear: z.string().optional(),
});

const IncidentDetailSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  impact_summary: z.string(),
  status: z.enum(STATUS_OPTIONS),
  severity: z.enum(SEVERITY_OPTIONS),
  service_tier: z.enum(SERVICE_TIER_OPTIONS).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  is_private: z.boolean(),
  affected_area_tags: z.array(z.string()),
  root_cause_tags: z.array(z.string()),
  impact_tags: z.array(z.string()),
  participants: z.array(ParticipantSchema),
  external_links: ExternalLinksSchema,
  time_started: z.string().nullable(),
  time_detected: z.string().nullable(),
  time_analyzed: z.string().nullable(),
  time_mitigated: z.string().nullable(),
  time_recovered: z.string().nullable(),
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
