import {infiniteQueryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import {ServiceTierSchema, SeveritySchema, StatusSchema} from '../types';

const IncidentListItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  status: StatusSchema,
  severity: SeveritySchema,
  service_tier: ServiceTierSchema.nullable(),
  created_at: z.string(),
  is_private: z.boolean(),
});

const PaginatedIncidentsSchema = z.object({
  count: z.number(),
  next: z.string().nullable(),
  previous: z.string().nullable(),
  results: z.array(IncidentListItemSchema),
});

export type IncidentListItem = z.infer<typeof IncidentListItemSchema>;
export type PaginatedIncidents = z.infer<typeof PaginatedIncidentsSchema>;

interface IncidentsQueryArgs {
  status?: string[];
  severity?: string[];
  service_tier?: string[];
  affected_service?: string[];
  root_cause?: string[];
  impact_type?: string[];
  affected_region?: string[];
  captain?: string[];
  reporter?: string[];
  created_after?: string;
  created_before?: string;
}

export function incidentsQueryOptions(args: IncidentsQueryArgs) {
  return infiniteQueryOptions({
    queryKey: ['Incidents', args],
    queryFn: ({signal, pageParam}) =>
      Api.get({
        path: '/ui/incidents/',
        query: {...args, page: pageParam},
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
