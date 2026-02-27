import {z} from 'zod';

export const StatusSchema = z.enum([
  'Active',
  'Mitigated',
  'Postmortem',
  'Done',
  'Cancelled',
]);

export const SeveritySchema = z.enum(['P0', 'P1', 'P2', 'P3', 'P4']);

export const ServiceTierSchema = z.enum(['T0', 'T1', 'T2', 'T3', 'T4']);

export type IncidentStatus = z.infer<typeof StatusSchema>;

export const STATUS_FILTER_GROUPS = {
  active: ['Active', 'Mitigated'] as IncidentStatus[],
  review: ['Postmortem'] as IncidentStatus[],
  closed: ['Done', 'Cancelled'] as IncidentStatus[],
};
