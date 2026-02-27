import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {useNavigate, useSearch} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Pill} from 'components/Pill';
import {Tag} from 'components/Tag';
import {SlidersHorizontalIcon, XIcon} from 'lucide-react';

import {tagsQueryOptions, type TagType} from '../$incidentId/queries/tagsQueryOptions';
import {ServiceTierSchema, SeveritySchema} from '../types';

import {DateFilter} from './DateFilter';
import {MultiSelectFilter} from './MultiSelectFilter';
import {TextInputFilter} from './TextInputFilter';

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

function hasAdvancedFilters(search: Record<string, unknown>): boolean {
  for (const key of ARRAY_FILTER_KEYS) {
    const val = search[key];
    if (Array.isArray(val) && val.length > 0) return true;
  }
  if (search.created_after || search.created_before) return true;
  return false;
}

export function AdvancedFilters() {
  const search = useSearch({from: '/'});
  const navigate = useNavigate();
  const [open, setOpen] = useState(() => hasAdvancedFilters(search));

  function updateArrayFilter(key: ArrayFilterKey, value: string) {
    const current = (search[key] as string[] | undefined) ?? [];
    const next = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];
    navigate({
      to: '/',
      search: prev => ({...prev, [key]: next.length > 0 ? next : undefined}),
    });
  }

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

  const activeFilters: {key: ArrayFilterKey; value: string; label: string}[] = [];
  for (const key of ARRAY_FILTER_KEYS) {
    const values = (search[key] as string[] | undefined) ?? [];
    for (const value of values) {
      activeFilters.push({key, value, label: FILTER_LABELS[key]});
    }
  }

  const hasActive =
    activeFilters.length > 0 || !!search.created_after || !!search.created_before;

  return (
    <div data-testid="advanced-filters">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setOpen(prev => !prev)}
        data-testid="advanced-filters-toggle"
      >
        <SlidersHorizontalIcon className="h-3.5 w-3.5" />
        Filters
        {hasActive && (
          <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-2xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
            {activeFilters.length +
              (search.created_after ? 1 : 0) +
              (search.created_before ? 1 : 0)}
          </span>
        )}
      </Button>

      {open && (
        <div className="mt-space-md flex flex-col gap-space-md">
          <div className="flex flex-wrap gap-space-xs">
            <MultiSelectFilter
              label="Severity"
              options={SeveritySchema.options}
              selected={(search.severity as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('severity', v)}
              renderOption={v => <Pill variant={v as 'P0'}>{v}</Pill>}
            />
            <MultiSelectFilter
              label="Service Tier"
              options={ServiceTierSchema.options}
              selected={(search.service_tier as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('service_tier', v)}
              renderOption={v => <Pill variant={v as 'T0'}>{v}</Pill>}
            />
            <TagMultiSelect
              label="Affected Service"
              tagType="AFFECTED_SERVICE"
              selected={(search.affected_service as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('affected_service', v)}
            />
            <TagMultiSelect
              label="Root Cause"
              tagType="ROOT_CAUSE"
              selected={(search.root_cause as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('root_cause', v)}
            />
            <TagMultiSelect
              label="Impact Type"
              tagType="IMPACT_TYPE"
              selected={(search.impact_type as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('impact_type', v)}
            />
            <TagMultiSelect
              label="Affected Region"
              tagType="AFFECTED_REGION"
              selected={(search.affected_region as string[] | undefined) ?? []}
              onToggle={v => updateArrayFilter('affected_region', v)}
            />
            <TextInputFilter
              label="Captain"
              values={(search.captain as string[] | undefined) ?? []}
              onAdd={v => updateArrayFilter('captain', v)}
              onRemove={v => removeArrayFilterValue('captain', v)}
              placeholder="Enter email"
            />
            <TextInputFilter
              label="Reporter"
              values={(search.reporter as string[] | undefined) ?? []}
              onAdd={v => updateArrayFilter('reporter', v)}
              onRemove={v => removeArrayFilterValue('reporter', v)}
              placeholder="Enter email"
            />
            <DateFilter
              label="Created After"
              value={search.created_after}
              onChange={v => updateDateFilter('created_after', v)}
            />
            <DateFilter
              label="Created Before"
              value={search.created_before}
              onChange={v => updateDateFilter('created_before', v)}
            />
          </div>

          {hasActive && (
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
      )}
    </div>
  );
}

function TagMultiSelect({
  label,
  tagType,
  selected,
  onToggle,
}: {
  label: string;
  tagType: TagType;
  selected: string[];
  onToggle: (value: string) => void;
}) {
  const {data: options = []} = useQuery(tagsQueryOptions(tagType));

  return (
    <MultiSelectFilter
      label={label}
      options={options}
      selected={selected}
      onToggle={onToggle}
      searchable
    />
  );
}
