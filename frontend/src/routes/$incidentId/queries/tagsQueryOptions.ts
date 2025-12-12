import {queryOptions, type QueryClient} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const TagsSchema = z.array(z.string());
const TagTypeSchema = z.enum(['AFFECTED_AREA', 'ROOT_CAUSE']);
const CreateTagResponseSchema = z.object({name: z.string(), type: TagTypeSchema});

export type TagType = z.infer<typeof TagTypeSchema>;

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
        responseSchema: CreateTagResponseSchema,
      }),
    onMutate: async ({name, type}: CreateTagArgs) => {
      await queryClient.cancelQueries({queryKey: ['Tags', type]});
      const previousTags = queryClient.getQueryData<string[]>(['Tags', type]);
      queryClient.setQueryData<string[]>(['Tags', type], old => [...(old ?? []), name]);
      return {previousTags};
    },
    onError: (
      _error: Error,
      variables: CreateTagArgs,
      context: {previousTags: string[] | undefined} | undefined
    ) => {
      if (context?.previousTags) {
        queryClient.setQueryData(['Tags', variables.type], context.previousTags);
      }
    },
    onSettled: (_data: unknown, _error: unknown, variables: CreateTagArgs) => {
      queryClient.invalidateQueries({queryKey: ['Tags', variables.type]});
    },
  };
}
