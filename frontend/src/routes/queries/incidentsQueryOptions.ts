import {infiniteQueryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

export const IncidentStatusSchema = z.enum([
  'Active',
  'Mitigated',
  'Postmortem',
  'Done',
  'Cancelled',
]);

const IncidentListItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  status: IncidentStatusSchema,
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  service_tier: z.enum(['T0', 'T1', 'T2', 'T3', 'T4']).nullable(),
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
  return infiniteQueryOptions({
    queryKey: ['Incidents', status],
    queryFn: ({signal, pageParam}) =>
      Api.get({
        path: '/ui/incidents/',
        query: {status, page: pageParam},
        signal,
        responseSchema: PaginatedIncidentsSchema,
      }),
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      // Extract page number from next URL, or return undefined if no next page
      if (!lastPage.next) return undefined;

      const url = new URL(lastPage.next);
      const page = url.searchParams.get('page');
      return page ? parseInt(page, 10) : undefined;
    },
    select: data => data.pages.flatMap(page => page.results),
  });
}
