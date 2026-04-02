import {infiniteQueryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const UserSchema = z.object({
  email: z.string(),
  name: z.string(),
  avatar_url: z.string().nullable(),
});

const PaginatedUsersSchema = z.object({
  count: z.number(),
  next: z.string().nullable(),
  previous: z.string().nullable(),
  results: z.array(UserSchema),
});

export type User = z.infer<typeof UserSchema>;

export function usersInfiniteQueryOptions(search?: string) {
  return infiniteQueryOptions({
    queryKey: ['Users', {search}],
    queryFn: ({signal, pageParam}) =>
      Api.get({
        path: '/users/',
        query: {...(search ? {search} : {}), page: pageParam},
        signal,
        responseSchema: PaginatedUsersSchema,
      }),
    initialPageParam: 1,
    getNextPageParam: lastPage => {
      if (!lastPage.next) return undefined;
      const url = new URL(lastPage.next);
      const page = url.searchParams.get('page');
      return page ? parseInt(page, 10) : undefined;
    },
    select: data => data.pages.flatMap(page => page.results),
  });
}
