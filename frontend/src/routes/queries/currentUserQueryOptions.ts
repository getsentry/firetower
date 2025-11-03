import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const CurrentUserSchema = z.object({
  name: z.string(),
  avatar_url: z.string().nullable(),
});

export type CurrentUser = z.infer<typeof CurrentUserSchema>;

export function currentUserQueryOptions() {
  return queryOptions({
    queryKey: ['CurrentUser'],
    queryFn: ({signal}) =>
      Api.get({
        path: '/ui/users/me/',
        signal,
        responseSchema: CurrentUserSchema,
      }),
  });
}
