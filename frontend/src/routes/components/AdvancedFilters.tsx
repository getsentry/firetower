import {useNavigate, useSearch} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Tag} from 'components/Tag';
import {SlidersHorizontalIcon, XIcon} from 'lucide-react';

type ArrayFilterKey =
  | 'severity'
  | 'service_tier'
  | 'affected_service'
  | 'root_cause'
  | 'impact_type'
  | 'affected_region'
  | 'captain'
  | 'reporter';

type DateFilterKey = 'created_after' | 'created_before';

const FILTER_LABELS: Record<ArrayFilterKey | DateFilterKey, string> = {
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

const ARRAY_FILTER_KEYS: ArrayFilterKey[] = [
  'severity',
  'service_tier',
  'affected_service',
  'root_cause',
  'impact_type',
  'affected_region',
  'captain',
  'reporter',
];

function useActiveFilters() {
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

export function FilterTrigger({open, onToggle}: {open: boolean; onToggle: () => void}) {
  const {activeCount} = useActiveFilters();

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={onToggle}
      aria-expanded={open}
      data-testid="advanced-filters-toggle"
    >
      <SlidersHorizontalIcon className="h-3.5 w-3.5" />
      Filter
      {activeCount > 0 && (
        <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-2xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
          {activeCount}
        </span>
      )}
    </Button>
  );
}

export function FilterPanel() {
  const navigate = useNavigate();
  const {search, activeFilters, activeCount} = useActiveFilters();

  function removeArrayFilterValue(key: ArrayFilterKey, value: string) {
    const current = (search[key] as string[] | undefined) ?? [];
    const next = current.filter(v => v !== value);
    navigate({
      to: '/',
      search: prev => ({...prev, [key]: next.length > 0 ? next : undefined}),
    });
  }

  function updateDateFilter(key: DateFilterKey, value: string | undefined) {
    navigate({
      to: '/',
      search: prev => ({...prev, [key]: value}),
    });
  }

  function clearAll() {
    navigate({
      to: '/',
      search: prev => {
        const next = {...prev};
        for (const key of ARRAY_FILTER_KEYS) {
          delete next[key];
        }
        delete next.created_after;
        delete next.created_before;
        return next;
      },
    });
  }

  return (
    <div
      className="bg-background-secondary flex flex-col gap-space-md rounded-md p-space-md"
      data-testid="advanced-filters"
    >
      <div className="grid grid-cols-2 gap-space-md">
        <div>Column 1</div>
        <div>Column 2</div>
      </div>

      {activeCount > 0 && (
        <div className="flex flex-wrap items-center gap-space-xs">
          {activeFilters.map(({key, value, label}) => (
            <Tag
              key={`${key}-${value}`}
              action={
                <button
                  type="button"
                  onClick={() => removeArrayFilterValue(key, value)}
                  className="text-content-secondary hover:text-content-primary cursor-pointer"
                >
                  <XIcon className="h-3 w-3" />
                </button>
              }
            >
              {label}: {value}
            </Tag>
          ))}
          {search.created_after && (
            <Tag
              action={
                <button
                  type="button"
                  onClick={() => updateDateFilter('created_after', undefined)}
                  className="text-content-secondary hover:text-content-primary cursor-pointer"
                >
                  <XIcon className="h-3 w-3" />
                </button>
              }
            >
              After: {search.created_after}
            </Tag>
          )}
          {search.created_before && (
            <Tag
              action={
                <button
                  type="button"
                  onClick={() => updateDateFilter('created_before', undefined)}
                  className="text-content-secondary hover:text-content-primary cursor-pointer"
                >
                  <XIcon className="h-3 w-3" />
                </button>
              }
            >
              Before: {search.created_before}
            </Tag>
          )}
          <button
            type="button"
            onClick={clearAll}
            className="text-content-accent text-size-sm cursor-pointer hover:underline"
            data-testid="clear-all-filters"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}
