import {Link} from '@tanstack/react-router';
import {cn} from 'utils/cn';

import {type Period} from '../queries/availabilityQueryOptions';

const TABS: {value: Period; label: string}[] = [
  {value: 'month', label: 'Month'},
  {value: 'quarter', label: 'Quarter'},
  {value: 'year', label: 'Year'},
];

interface PeriodTabsProps {
  activePeriod: Period;
}

export function PeriodTabs({activePeriod}: PeriodTabsProps) {
  return (
    <div className="gap-space-2xs flex">
      {TABS.map(tab => (
        <Link
          key={tab.value}
          to="/availability"
          search={{period: tab.value}}
          preload="intent"
          className={cn(
            'rounded-radius-sm px-space-lg py-space-sm text-size-sm font-medium transition-colors',
            {
              'bg-background-primary dark:bg-background-transparent-neutral-muted text-content-headings shadow-sm':
                activePeriod === tab.value,
              'text-content-secondary hover:text-black dark:hover:text-white':
                activePeriod !== tab.value,
            }
          )}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
