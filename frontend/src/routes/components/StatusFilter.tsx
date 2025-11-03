import {Link, useSearch} from '@tanstack/react-router';
import {cn} from 'utils/cn';

import {type IncidentStatus} from '../queries/incidentsQueryOptions';
import {STATUS_FILTER_GROUPS} from '../types';

interface FilterLinkProps {
  statuses: IncidentStatus[];
  label: string;
  isActive: boolean;
  testId?: string;
}

function arraysEqual(a: IncidentStatus[], b: IncidentStatus[]): boolean {
  if (a.length !== b.length) return false;
  const setB = new Set(b);
  return a.every(val => setB.has(val));
}

function FilterLink({statuses, label, isActive, testId}: FilterLinkProps) {
  return (
    <Link
      to="/"
      search={{status: statuses}}
      preload="intent"
      data-testid={testId}
      aria-selected={isActive}
      className={cn(
        'rounded-radius-sm px-space-lg py-space-sm text-size-sm font-medium transition-colors',
        {
          'bg-background-primary text-content-headings shadow-sm': isActive,
          'text-content-secondary hover:text-black': !isActive,
        }
      )}
    >
      {label}
    </Link>
  );
}

export function StatusFilter() {
  const {status} = useSearch({from: '/'});

  return (
    <div className="gap-space-2xs flex">
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.active}
        label="Active"
        isActive={arraysEqual(status, STATUS_FILTER_GROUPS.active)}
        testId="filter-active"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.review}
        label="In Review"
        isActive={arraysEqual(status, STATUS_FILTER_GROUPS.review)}
        testId="filter-review"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.closed}
        label="Closed"
        isActive={arraysEqual(status, STATUS_FILTER_GROUPS.closed)}
        testId="filter-closed"
      />
    </div>
  );
}
