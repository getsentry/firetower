import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

import {ActionItemSchema} from '../../$incidentId/queries/actionItemsQueryOptions';
import {SeveritySchema} from '../../types';

export const TimeRangeSchema = z.enum([
  '7d',
  '14d',
  '1m',
  '3m',
  '6m',
  '9m',
  '12m',
  'all',
]);
export const TIME_RANGE_OPTIONS = [
  {value: '7d', label: '7d', description: 'Last 7 days'},
  {value: '14d', label: '14d', description: 'Last 14 days'},
  {value: '1m', label: '1m', description: 'Last month'},
  {value: '3m', label: '3m', description: 'Last 3 months'},
  {value: '6m', label: '6m', description: 'Last 6 months'},
  {value: '9m', label: '9m', description: 'Last 9 months'},
  {value: '12m', label: '12m', description: 'Last 12 months'},
  {value: 'all', label: 'All time', description: 'Entire cached history'},
] as const;

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
  time_range: TimeRangeSchema.optional().catch(undefined),
  severity: SeveritySchema.optional().catch(undefined),
  view: QueueViewSchema.optional().catch(undefined),
  team: z
    .union([z.uuid(), z.literal('unknown')])
    .optional()
    .catch(undefined),
  q: z.string().trim().max(200).optional().catch(undefined),
  page: z.number().int().min(1).max(100000).optional().catch(undefined),
});

const DashboardItemSchema = ActionItemSchema.omit({
  assignee_name: true,
  assignee_avatar_url: true,
}).extend({
  id: z.number(),
  incident_id: z.string(),
  incident_title: z.string(),
  incident_severity: z.string(),
  linear_team_id: z.string(),
  linear_team_key: z.string(),
  linear_team_name: z.string(),
  deadline_source: z.enum(['linear_due_date', 'linear_sla', 'priority_slo']).nullable(),
  due_date: z.string().nullable(),
  created_at: z.string(),
  linear_updated_at: z.string().nullable(),
  age_days: z.number(),
  idle_days: z.number().nullable(),
  flags: z.array(z.enum(['overdue', 'due_soon', 'stalled', 'unassigned', 'no_priority'])),
});

const DashboardTeamSchema = z.object({
  id: z.string(),
  name: z.string(),
  key: z.string(),
  open: z.number(),
  overdue: z.number(),
  stalled: z.number(),
  completed: z.number(),
  canceled: z.number(),
  total: z.number(),
  completion_rate: z.number().nullable(),
});

export const DashboardSchema = z.object({
  generated_at: z.string(),
  time_range: z.object({
    key: TimeRangeSchema,
    label: z.string(),
    start: z.string().nullable(),
    end: z.string(),
  }),
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
    created_count: z.number(),
    completed_count: z.number(),
    median_completion_days: z.number().nullable(),
    on_time_percent: z.number().nullable(),
    on_time_sample: z.number(),
    unknown_activity: z.number(),
    unknown_team: z.number(),
    unknown_completion: z.number(),
  }),
  trend: z.object({
    interval: z.string(),
    buckets: z.array(
      z.object({
        start: z.string(),
        end: z.string(),
        label: z.string(),
        created: z.number(),
        completed: z.number(),
      })
    ),
  }),
  aging: z.array(z.object({label: z.string(), count: z.number(), overdue: z.number()})),
  teams: z.array(DashboardTeamSchema),
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
export type DashboardTeam = z.infer<typeof DashboardTeamSchema>;
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
