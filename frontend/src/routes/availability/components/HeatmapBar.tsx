import {Link} from '@tanstack/react-router';
import {cn} from 'utils/cn';

import {getAvailabilityLevel, type AvailabilityLevel} from '../utils';

const AVAILABILITY_BG: Record<AvailabilityLevel, string> = {
  success: 'bg-graphics-success-moderate',
  warning: 'bg-graphics-warning-moderate',
  danger: 'bg-graphics-danger-moderate',
};

interface HeatmapBlock {
  label: string;
  availability: number;
  periodStart: string;
  periodEnd: string;
  regionName: string;
}

interface HeatmapBarProps {
  blocks: HeatmapBlock[];
  showEndLabels?: boolean;
}

export function HeatmapBar({blocks, showEndLabels}: HeatmapBarProps) {
  return (
    <div className="flex gap-px overflow-visible">
      {blocks.map((block, i) => {
        const inner = (
          <>
            <div
              className={cn(
                'flex h-8 items-center justify-center sm:transition-opacity sm:group-hover:opacity-80',
                AVAILABILITY_BG[getAvailabilityLevel(block.availability)],
                i === 0 && 'rounded-l-md',
                i === blocks.length - 1 && 'rounded-r-md'
              )}
            >
              <span className="font-mono text-size-sm font-medium text-white drop-shadow-md">
                {block.availability.toFixed(2)}%
              </span>
            </div>
            <div
              className={cn(
                'pointer-events-none absolute top-full left-1/2 z-10 mt-0.5 -translate-x-1/2 whitespace-nowrap sm:block',
                showEndLabels && i === blocks.length - 1
                  ? 'opacity-100'
                  : 'hidden opacity-0 transition-opacity group-hover:opacity-100'
              )}
            >
              <span className="text-size-xs text-content-secondary">{block.label}</span>
            </div>
          </>
        );

        return block.availability >= 100 ? (
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
