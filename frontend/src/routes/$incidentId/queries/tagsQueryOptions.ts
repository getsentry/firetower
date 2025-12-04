import {queryOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const TagsSchema = z.array(z.string());
const TagSchema = z.string();

export type TagType = 'AFFECTED_AREA' | 'ROOT_CAUSE';

export function tagsQueryOptions(type: TagType) {
  return queryOptions({
    queryKey: ['Tags', type],
    queryFn: ({signal}) =>
      Api.get({
        path: '/tags/',
        query: {type},
        signal,
        responseSchema: TagsSchema,
      }),
  });
}

interface CreateTagArgs {
  name: string;
  type: TagType;
}

export function createTagMutationOptions(queryClient: QueryClient) {
  return {
    mutationFn: ({name, type}: CreateTagArgs) =>
      Api.post({
        path: '/tags/',
        body: {name, type},
        responseSchema: TagSchema,
      }),
    onSuccess: (_data: string, variables: CreateTagArgs) => {
      queryClient.invalidateQueries({queryKey: ['Tags', variables.type]});
    },
  };
}
