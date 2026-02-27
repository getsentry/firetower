import {Link, useSearch} from '@tanstack/react-router';
import {arraysEqual} from 'utils/arrays';
import {cn} from 'utils/cn';

import {STATUS_FILTER_GROUPS, type IncidentStatus} from '../types';

interface FilterLinkProps {
  statuses?: IncidentStatus[];
  label: string;
  isActive: boolean;
  testId?: string;
}

function FilterLink({statuses, label, isActive, testId}: FilterLinkProps) {
  return (
    <Link
      to="/"
      search={prev => ({...prev, status: statuses})}
      preload="intent"
      data-testid={testId}
      aria-selected={isActive}
      className={cn(
        'rounded-radius-sm px-space-lg py-space-sm text-size-sm font-medium transition-colors',
        {
          'bg-background-primary dark:bg-background-transparent-neutral-muted text-content-headings shadow-sm':
            isActive,
          'text-content-secondary hover:text-black dark:hover:text-white': !isActive,
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
        statuses={undefined}
        label="Active"
        isActive={
          status === undefined || arraysEqual(status, STATUS_FILTER_GROUPS.active)
        }
        testId="filter-active"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.review}
        label="In Review"
        isActive={arraysEqual(status ?? [], STATUS_FILTER_GROUPS.review)}
        testId="filter-review"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.closed}
        label="Closed"
        isActive={arraysEqual(status ?? [], STATUS_FILTER_GROUPS.closed)}
        testId="filter-closed"
      />
    </div>
  );
}
