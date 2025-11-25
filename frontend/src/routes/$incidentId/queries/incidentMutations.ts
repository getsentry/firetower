import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Api} from 'api';

import {IncidentDetailSchema} from './incidentDetailQueryOptions';

interface UpdateIncidentFieldArgs {
  incidentId: string;
  field: 'severity' | 'status';
  value: string;
}

export function useUpdateIncidentField() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({incidentId, field, value}: UpdateIncidentFieldArgs) => {
      return Api.patch({
        path: `/incidents/${incidentId}/`,
        body: {[field]: value},
        responseSchema: IncidentDetailSchema,
      });
    },
    onSuccess: (data, variables) => {
      queryClient.setQueryData(['IncidentDetail', variables.incidentId], data);
    },
  });
}
