import {mutationOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import type {TagType} from './tagsQueryOptions';

const CreateTagResponseSchema = z.object({
  name: z.string(),
  type: z.string(),
});

export function createTagMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: async ({name, type}: {name: string; type: TagType}) => {
      return Api.post({
        path: '/tags/',
        body: {name, type},
        responseSchema: CreateTagResponseSchema,
      });
    },
    onSuccess: (_data, variables) => {
      // Invalidate the tags query to refetch with the new tag
      queryClient.invalidateQueries({queryKey: ['Tags', variables.type]});
    },
  });
}
