import {Link} from '@tanstack/react-router';
import {cn} from 'utils/cn';

import type {Period} from '../queries/availabilityQueryOptions';

interface PeriodTabProps {
  period: Period;
  label: string;
  isActive: boolean;
}

export function PeriodTab({period, label, isActive}: PeriodTabProps) {
  return (
    <Link
      to="/availability"
      search={{period}}
      preload="intent"
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
