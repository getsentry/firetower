import {queryOptions} from '@tanstack/react-query';
import {z} from 'zod';

import {Api} from '../api';

const IncidentListItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  status: z.enum(['Active', 'Mitigated', 'Postmortem', 'Actions Pending', 'Done']),
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  created_at: z.string(),
  is_private: z.boolean(),
});

const IncidentsListSchema = z.array(IncidentListItemSchema);

interface IncidentsQueryArgs {
  status?: string;
}

export function incidentsQueryOptions({status}: IncidentsQueryArgs) {
  return queryOptions({
    queryKey: ['Incidents', status],
    queryFn: ({signal}) =>
      Api.get({
        path: '/ui/incidents/',
        query: {status},
        signal,
        responseSchema: IncidentsListSchema,
      }),
  });
}

const ParticipantSchema = z.object({
  name: z.string(),
  slack: z.string(),
  avatar_url: z.string(),
  role: z.enum(['Captain', 'Reporter']).nullable(),
});

const ExternalLinksSchema = z.object({
  slack: z.string().nullable(),
  jira: z.string().nullable(),
  datadog: z.string().nullable(),
  pagerduty: z.string().nullable(),
  statuspage: z.string().nullable(),
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
