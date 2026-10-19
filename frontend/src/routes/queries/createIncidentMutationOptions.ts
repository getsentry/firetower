import {mutationOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import {SeveritySchema} from '../types';

const CreateIncidentResponseSchema = z.object({
  id: z.string(),
  title: z.string(),
  severity: SeveritySchema,
});

export interface CreateIncidentArgs {
  title: string;
  severity: string;
  description?: string;
  captain: string;
  reporter: string;
}

export type CreateIncidentResponse = z.infer<typeof CreateIncidentResponseSchema>;

export function createIncidentMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async (args: CreateIncidentArgs) => {
      return Api.post({
        path: '/incidents/',
        body: args,
        responseSchema: CreateIncidentResponseSchema,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({queryKey: ['Incidents']});
    },
  });
}
