import {useSearch} from '@tanstack/react-router';

export type ArrayFilterKey =
  | 'severity'
  | 'service_tier'
  | 'affected_service'
  | 'root_cause'
  | 'impact_type'
  | 'affected_region'
  | 'captain'
  | 'reporter';

export type DateFilterKey = 'created_after' | 'created_before';

export const FILTER_LABELS: Record<ArrayFilterKey | DateFilterKey, string> = {
  severity: 'Severity',
  service_tier: 'Service Tier',
  affected_service: 'Affected Service',
  root_cause: 'Root Cause',
  impact_type: 'Impact Type',
  affected_region: 'Affected Region',
  captain: 'Captain',
  reporter: 'Reporter',
  created_after: 'Created After',
  created_before: 'Created Before',
};

export const ARRAY_FILTER_KEYS: ArrayFilterKey[] = [
  'severity',
  'service_tier',
  'affected_service',
  'root_cause',
  'impact_type',
  'affected_region',
  'captain',
  'reporter',
];

export function useActiveFilters() {
  const search = useSearch({from: '/'});

  const activeFilters: {key: ArrayFilterKey; value: string; label: string}[] = [];
  for (const key of ARRAY_FILTER_KEYS) {
    const values = (search[key] as string[] | undefined) ?? [];
    for (const value of values) {
      activeFilters.push({key, value, label: FILTER_LABELS[key]});
    }
  }

  const activeCount =
    activeFilters.length +
    (search.created_after ? 1 : 0) +
    (search.created_before ? 1 : 0);

  return {search, activeFilters, activeCount};
}
