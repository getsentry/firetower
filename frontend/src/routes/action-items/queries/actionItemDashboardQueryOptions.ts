import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import {ActionItemSchema} from '../../$incidentId/queries/actionItemsQueryOptions';

export const QueueViewSchema = z.enum([
  'attention',
  'open',
  'overdue',
  'due_soon',
  'stalled',
  'unassigned',
  'no_priority',
]);
export const DashboardSearchSchema = z.object({
  severity: z.enum(['P0', 'P1', 'P2', 'P3', 'P4']).optional().catch(undefined),
  view: QueueViewSchema.optional().catch(undefined),
  assignee: z
    .string()
    .regex(/^(unassigned|[0-9]+)$/)
    .optional()
    .catch(undefined),
  q: z.string().trim().max(200).optional().catch(undefined),
  page: z.number().int().min(1).max(100000).optional().catch(undefined),
});

const DashboardItemSchema = ActionItemSchema.extend({
  id: z.number(),
  incident_id: z.string(),
  incident_title: z.string(),
  incident_severity: z.string(),
  assignee_id: z.number().nullable(),
  created_at: z.string(),
  linear_updated_at: z.string().nullable(),
  age_days: z.number(),
  idle_days: z.number().nullable(),
  flags: z.array(z.enum(['overdue', 'due_soon', 'stalled', 'unassigned', 'no_priority'])),
});

export const DashboardSchema = z.object({
  generated_at: z.string(),
  stalled_days: z.number(),
  due_soon_days: z.number(),
  summary: z.object({
    open: z.number(),
    in_progress: z.number(),
    todo: z.number(),
    done: z.number(),
    canceled: z.number(),
    high_priority_open: z.number(),
    overdue: z.number(),
    due_soon: z.number(),
    stalled: z.number(),
    unassigned: z.number(),
    no_priority: z.number(),
    attention: z.number(),
    created_30d: z.number(),
    completed_30d: z.number(),
    median_completion_days: z.number().nullable(),
    on_time_percent: z.number().nullable(),
    on_time_sample: z.number(),
    unknown_activity: z.number(),
    unknown_completion: z.number(),
  }),
  weeks: z.array(
    z.object({start: z.string(), created: z.number(), completed: z.number()})
  ),
  aging: z.array(z.object({label: z.string(), count: z.number(), overdue: z.number()})),
  owners: z.array(
    z.object({
      id: z.string(),
      name: z.string(),
      open: z.number(),
      overdue: z.number(),
      stalled: z.number(),
    })
  ),
  freshness: z.object({
    linked_incidents: z.number(),
    unlinked_incidents: z.number(),
    unsynced_incidents: z.number(),
    stale_incidents: z.number(),
    oldest_sync_at: z.string().nullable(),
  }),
  queue: z.object({
    count: z.number(),
    page: z.number(),
    pages: z.number(),
    results: z.array(DashboardItemSchema),
  }),
});

export type DashboardData = z.infer<typeof DashboardSchema>;
export type DashboardItem = z.infer<typeof DashboardItemSchema>;
export type DashboardSearch = z.infer<typeof DashboardSearchSchema>;
export type QueueView = z.infer<typeof QueueViewSchema>;

export const actionItemDashboardQueryOptions = (search: DashboardSearch = {}) =>
  queryOptions({
    queryKey: ['ActionItemDashboard', search],
    queryFn: ({signal}) =>
      Api.get({
        path: '/ui/action-items/',
        query: search,
        signal,
        responseSchema: DashboardSchema,
      }),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
