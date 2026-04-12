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

  let activeCount = 0;
  for (const key of ARRAY_FILTER_KEYS) {
    const values = (search[key] as string[] | undefined) ?? [];
    activeCount += values.length;
  }
  if (search.created_after) activeCount++;
  if (search.created_before) activeCount++;

  return {search, activeCount};
}
