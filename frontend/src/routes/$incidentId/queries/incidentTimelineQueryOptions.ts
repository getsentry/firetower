import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const TimelineEventSourceSchema = z.enum(['USER', 'INTERNAL', 'STATUSPAGE', 'PAGERDUTY']);

const TimelineEventTypeSchema = z.enum([
  'note',
  'incident_created',
  'status_changed',
  'severity_changed',
  'captain_changed',
  'title_changed',
  'visibility_changed',
  'statuspage_incident_created',
  'statuspage_update_posted',
  'pagerduty_incident_triggered',
]);

const TimelineActorSchema = z.object({
  email: z.string(),
  name: z.string(),
  avatar_url: z.string().nullable(),
});

const TimelineEventSchema = z.object({
  id: z.number().int(),
  source: TimelineEventSourceSchema,
  event_type: TimelineEventTypeSchema,
  occurred_at: z.string(),
  created_at: z.string(),
  actor: TimelineActorSchema.nullable(),
  summary: z.string(),
  payload: z.record(z.string(), z.unknown()),
  link_url: z.union([z.url(), z.literal('')]),
  external_id: z.string(),
});

export type TimelineEvent = z.infer<typeof TimelineEventSchema>;
export type TimelineEventSource = z.infer<typeof TimelineEventSourceSchema>;

interface IncidentTimelineQueryArgs {
  incidentId: string;
}

export function incidentTimelineQueryOptions({incidentId}: IncidentTimelineQueryArgs) {
  return queryOptions({
    queryKey: ['IncidentTimeline', incidentId],
    queryFn: ({signal}) =>
      Api.get({
        path: `/ui/incidents/${incidentId}/timeline-events/`,
        signal,
        responseSchema: z.array(TimelineEventSchema),
      }),
  });
}
