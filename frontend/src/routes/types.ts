import type {IncidentStatus} from './queries/incidentsQueryOptions';

export const STATUS_FILTER_GROUPS = {
  active: ['Active', 'Mitigated'] as IncidentStatus[],
  review: ['Postmortem', 'Actions Pending'] as IncidentStatus[],
  closed: ['Done'] as IncidentStatus[],
};
