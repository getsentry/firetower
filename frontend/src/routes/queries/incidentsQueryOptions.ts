import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

export const IncidentStatusSchema = z.enum([
  'Active',
  'Mitigated',
  'Postmortem',
  'Actions Pending',
  'Done',
]);

const IncidentListItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  status: IncidentStatusSchema,
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  created_at: z.string(),
  is_private: z.boolean(),
});

const PaginatedIncidentsSchema = z.object({
  count: z.number(),
  next: z.string().nullable(),
  previous: z.string().nullable(),
  results: z.array(IncidentListItemSchema),
});

export type IncidentStatus = z.infer<typeof IncidentStatusSchema>;
export type IncidentListItem = z.infer<typeof IncidentListItemSchema>;
export type PaginatedIncidents = z.infer<typeof PaginatedIncidentsSchema>;

interface IncidentsQueryArgs {
  status?: string[];
}

export function incidentsQueryOptions({status}: IncidentsQueryArgs) {
  return queryOptions({
    queryKey: ['Incidents', status],
    queryFn: ({signal}) =>
      Api.get({
        path: '/ui/incidents/',
        query: {status},
        signal,
        responseSchema: PaginatedIncidentsSchema,
      }),
  });
}
