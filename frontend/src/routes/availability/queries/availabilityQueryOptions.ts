import {queryOptions} from '@tanstack/react-query';
import {Api} from 'api';
import {z} from 'zod';

const IncidentSummarySchema = z.object({
  id: z.number(),
  title: z.string(),
  created_at: z.string(),
  total_downtime_minutes: z.number(),
  total_downtime_display: z.string().nullable(),
});

const RegionAvailabilitySchema = z.object({
  name: z.string(),
  total_downtime_minutes: z.number(),
  total_downtime_display: z.string().nullable(),
  availability_percentage: z.number(),
  incident_count: z.number(),
  incidents: z.array(IncidentSummarySchema),
});

const PeriodDataSchema = z.object({
  label: z.string(),
  start: z.string(),
  end: z.string(),
  regions: z.array(RegionAvailabilitySchema),
});

const AvailabilitySchema = z.object({
  months: z.array(PeriodDataSchema),
  quarters: z.array(PeriodDataSchema),
  years: z.array(PeriodDataSchema),
});

export type RegionAvailability = z.infer<typeof RegionAvailabilitySchema>;
export type IncidentSummary = z.infer<typeof IncidentSummarySchema>;
export type PeriodData = z.infer<typeof PeriodDataSchema>;
export type AvailabilityData = z.infer<typeof AvailabilitySchema>;

export const availabilityQueryOptions = () =>
  queryOptions({
    queryKey: ['Availability'],
    queryFn: ({signal}) =>
      Api.get({
        path: '/ui/availability/',
        signal,
        responseSchema: AvailabilitySchema,
      }),
  });
