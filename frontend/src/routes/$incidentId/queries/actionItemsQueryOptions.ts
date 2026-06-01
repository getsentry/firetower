import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const ActionItemStatusSchema = z.enum(['Todo', 'In Progress', 'Done', 'Canceled']);

const ActionItemSchema = z.object({
  linear_identifier: z.string(),
  title: z.string(),
  status: ActionItemStatusSchema,
  priority: z.number().int(),
  assignee_name: z.string().nullable(),
  assignee_avatar_url: z.string().nullable(),
  url: z.string(),
});

export type ActionItem = z.infer<typeof ActionItemSchema>;
export type ActionItemStatus = z.infer<typeof ActionItemStatusSchema>;

interface ActionItemsQueryArgs {
  incidentId: string;
}

export function actionItemsQueryOptions({incidentId}: ActionItemsQueryArgs) {
  return queryOptions({
    queryKey: ['ActionItems', incidentId],
    queryFn: ({signal}) =>
      Api.get({
        path: `/ui/incidents/${incidentId}/action-items/`,
        signal,
        responseSchema: z.array(ActionItemSchema),
      }),
  });
}
