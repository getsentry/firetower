import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {SlidersHorizontalIcon} from 'lucide-react';

import {useActiveFilters} from '../useActiveFilters';

export function FilterTrigger({open, onToggle}: {open: boolean; onToggle: () => void}) {
  const navigate = useNavigate();
  const {activeCount} = useActiveFilters();

  return (
    <div className="flex items-center gap-space-md">
      {activeCount > 0 && (
        <button
          type="button"
          className="text-content-accent text-size-sm cursor-pointer hover:underline"
          onClick={() => {
            navigate({
              to: '/',
              search: prev => ({
                ...prev,
                severity: undefined,
                service_tier: undefined,
                affected_service: undefined,
                root_cause: undefined,
                impact_type: undefined,
                affected_region: undefined,
                captain: undefined,
                reporter: undefined,
                created_after: undefined,
                created_before: undefined,
                status: undefined,
              }),
              replace: true,
            });
          }}
          data-testid="clear-all-filters"
        >
          Clear all filters
        </button>
      )}
      <Button
        variant="secondary"
        size="sm"
        onClick={onToggle}
        aria-expanded={open}
        data-testid="advanced-filters-toggle"
      >
        <SlidersHorizontalIcon className="h-3.5 w-3.5" />
        {open ? 'Hide filters' : 'Show filters'}
        {activeCount > 0 && (
          <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-2xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
            {activeCount}
          </span>
        )}
      </Button>
    </div>
  );
}
