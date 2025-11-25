import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

interface UpdateIncidentFieldArgs {
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

export function useUpdateIncidentField() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({incidentId, field, value}: UpdateIncidentFieldArgs) => {
      return Api.patch({
        path: `/incidents/${incidentId}/`,
        body: {[field]: value},
        responseSchema: PatchResponseSchema,
      });
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({queryKey: ['IncidentDetail', variables.incidentId]});
    },
  });
}
