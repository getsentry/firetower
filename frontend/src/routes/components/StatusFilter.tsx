import {Link, useSearch} from '@tanstack/react-router';

import {cn} from '../../utils/cn';

type FilterValue = 'active' | 'review' | 'closed';

interface FilterLinkProps {
  value: FilterValue;
  label: string;
  isActive: boolean;
}

function FilterLink({value, label, isActive}: FilterLinkProps) {
  return (
    <Link
      to="/"
      search={{status: value}}
      preload="intent"
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
      <FilterLink value="active" label="Active" isActive={status === 'active'} />
      <FilterLink value="review" label="In Review" isActive={status === 'review'} />
      <FilterLink value="closed" label="Closed" isActive={status === 'closed'} />
    </div>
  );
}
