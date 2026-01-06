import {mutationOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import type {IncidentDetail} from './incidentDetailQueryOptions';
import {SEVERITY_OPTIONS, STATUS_OPTIONS} from './incidentDetailQueryOptions';

export type UpdateIncidentFieldArgs =
  | {
      incidentId: string;
      field:
        | 'severity'
        | 'status'
        | 'title'
        | 'description'
        | 'impact_summary'
        | 'captain'
        | 'reporter';
      value: string;
    }
  | {incidentId: string; field: 'is_private'; value: boolean}
  | {
      incidentId: string;
      field: 'affected_area_tags' | 'root_cause_tags' | 'impact_tags';
      value: string[];
    };

const PatchResponseSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  impact_summary: z.string(),
  status: z.enum(STATUS_OPTIONS),
  severity: z.enum(SEVERITY_OPTIONS),
  is_private: z.boolean(),
  affected_area_tags: z.array(z.string()),
  root_cause_tags: z.array(z.string()),
  impact_tags: z.array(z.string()),
});

export function updateIncidentFieldMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async ({incidentId, field, value}: UpdateIncidentFieldArgs) => {
      return Api.patch({
        path: `/incidents/${incidentId}/`,
        body: {[field]: value},
        responseSchema: PatchResponseSchema,
      });
    },
    onMutate: async variables => {
      await queryClient.cancelQueries({
        queryKey: ['IncidentDetail', variables.incidentId],
      });

      const previousIncident = queryClient.getQueryData([
        'IncidentDetail',
        variables.incidentId,
      ]);

      queryClient.setQueryData(
        ['IncidentDetail', variables.incidentId],
        (old: IncidentDetail | undefined) => {
          if (!old) return old;
          return {
            ...old,
            [variables.field]: variables.value,
          };
        }
      );

      return {previousIncident};
    },
    onError: (_err, variables, context) => {
      if (context?.previousIncident) {
        queryClient.setQueryData(
          ['IncidentDetail', variables.incidentId],
          context.previousIncident
        );
      }
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({queryKey: ['IncidentDetail', variables.incidentId]});
    },
  });
}
