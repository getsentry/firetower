import type {IncidentStatus} from './queries/incidentsQueryOptions';

export const STATUS_FILTER_GROUPS = {
  active: ['Active', 'Mitigated'] as IncidentStatus[],
  review: ['Postmortem'] as IncidentStatus[],
  closed: ['Done'] as IncidentStatus[],
};
