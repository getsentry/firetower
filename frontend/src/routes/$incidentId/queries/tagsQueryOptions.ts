import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const TagsSchema = z.array(z.string());

export type TagType = 'AFFECTED_AREA' | 'ROOT_CAUSE' | 'IMPACT_TYPE';

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
