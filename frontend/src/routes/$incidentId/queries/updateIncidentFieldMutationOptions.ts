import {mutationOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import type {IncidentDetail} from './incidentDetailQueryOptions';

export interface UpdateIncidentFieldArgs {
  incidentId: string;
  field: 'severity' | 'status';
  value: string;
}

const PatchResponseSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  impact: z.string(),
  status: z.enum(['Active', 'Mitigated', 'Postmortem', 'Actions Pending', 'Done']),
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']),
  is_private: z.boolean(),
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
