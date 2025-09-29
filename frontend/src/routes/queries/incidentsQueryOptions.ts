import {queryOptions} from '@tanstack/react-query';
import {z} from 'zod';

import {Api} from '../../api';

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

export type IncidentList = z.infer<typeof IncidentsListSchema>;

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
