import {mutationOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

export function syncActionItemsMutationOptions(
  queryClient: QueryClient,
  incidentId: string
) {
  return mutationOptions({
    mutationFn: async () => {
      return Api.post({
        path: `/incidents/${incidentId}/sync-action-items/`,
        responseSchema: z.object({success: z.boolean()}),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({queryKey: ['ActionItems', incidentId]});
    },
  });
}
