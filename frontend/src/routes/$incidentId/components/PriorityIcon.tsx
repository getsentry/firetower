import {Tooltip, TooltipContent, TooltipTrigger} from 'components/Tooltip';

const PRIORITY_CONFIG: Record<
  number,
  {bars?: number; urgent?: boolean; label: string; className: string}
> = {
  1: {
    urgent: true,
    label: 'Urgent (P1): interrupts normal work. SLA: 2 weeks.',
    className: 'text-content-secondary',
  },
  2: {
    bars: 3,
    label: 'High (P1): interrupts normal work. SLA: 2 weeks.',
    className: 'text-content-secondary',
  },
  3: {
    bars: 2,
    label: 'Medium (P2): scheduled ASAP. SLA: 4 weeks.',
    className: 'text-content-secondary',
  },
  4: {
    bars: 1,
    label: 'Low (P3): can be placed on the backlog.',
    className: 'text-content-secondary',
  },
};

const BAR_POSITIONS = [
  {x: 1, height: 4, y: 9},
  {x: 5, height: 7, y: 6},
  {x: 9, height: 10, y: 3},
];

export function PriorityIcon({priority}: {priority: number}) {
  const config = PRIORITY_CONFIG[priority];
  if (!config) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className={config.className}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            {config.urgent ? (
              <>
                <path
                  d="M7 1L13 12H1L7 1Z"
                  fill="currentColor"
                  fillOpacity="0.15"
                  stroke="currentColor"
                  strokeWidth="1"
                  strokeLinejoin="round"
                />
                <path
                  d="M7 5V8"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <circle cx="7" cy="10" r="0.75" fill="currentColor" />
              </>
            ) : (
              BAR_POSITIONS.map((bar, i) => (
                <rect
                  key={i}
                  x={bar.x}
                  y={bar.y}
                  width="3"
                  height={bar.height}
                  rx="0.5"
                  fill="currentColor"
                  opacity={i < config.bars! ? 1 : 0.2}
                />
              ))
            )}
          </svg>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <span className="text-content-primary text-xs">{config.label}</span>
      </TooltipContent>
    </Tooltip>
  );
}
