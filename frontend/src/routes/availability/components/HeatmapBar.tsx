import {Link} from '@tanstack/react-router';
import {cn} from 'utils/cn';

import {getAvailabilityLevel, type AvailabilityLevel} from '../utils';

const AVAILABILITY_BG: Record<AvailabilityLevel, string> = {
  success: 'bg-graphics-success-moderate',
  warning: 'bg-graphics-warning-moderate',
  danger: 'bg-graphics-danger-moderate',
};

interface HeatmapBlock {
  availability: number;
  periodStart: string;
  periodEnd: string;
  regionName: string;
}

interface HeatmapBarProps {
  blocks: HeatmapBlock[];
}

export function HeatmapBar({blocks}: HeatmapBarProps) {
  return (
    <div className="flex min-w-0 flex-1 gap-px overflow-visible">
      {blocks.map((block, i) => {
        const isFullUptime = block.availability >= 100;
        const displayPct = isFullUptime
          ? '100.00'
          : Math.min(99.99, block.availability).toFixed(2);
        const isLast = i === blocks.length - 1;
        const inner = (
          <>
            <div
              className={cn(
                'flex h-8 items-center justify-center',
                !isFullUptime && 'sm:transition-opacity sm:group-hover:opacity-80',
                AVAILABILITY_BG[getAvailabilityLevel(block.availability)],
                i === 0 && 'rounded-l-md',
                isLast && 'rounded-r-md'
              )}
            >
              <span className="text-size-sm font-mono font-medium text-white drop-shadow-md select-none">
                {displayPct}%
              </span>
            </div>
          </>
        );

        return isFullUptime ? (
          <div key={i} className="group relative min-w-0 flex-1">
            {inner}
          </div>
        ) : (
          <Link
            key={i}
            className="group relative min-w-0 flex-1"
            to="/"
            search={{
              affected_region: [block.regionName],
              created_after: block.periodStart,
              created_before: block.periodEnd,
              service_tier: ['T0'],
              impact_type: ['availability'],
              status: ['Any'],
            }}
          >
            {inner}
          </Link>
        );
      })}
    </div>
  );
}
