import {Tooltip, TooltipContent, TooltipTrigger} from 'components/Tooltip';
import {Info} from 'lucide-react';

export function AvailabilityTooltip() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          className="text-content-secondary hover:text-content-primary transition-colors"
          aria-label="How availability is calculated"
        >
          <Info size={18} />
        </button>
      </TooltipTrigger>
      <TooltipContent align="start" className="text-size-sm max-w-sm">
        <h3 className="text-content-headings mb-space-sm font-semibold">
          How availability is calculated
        </h3>
        <p className="text-content-secondary mb-space-sm">
          Availability percentage is calculated as:
        </p>
        <p className="text-content-primary bg-background-secondary mb-space-sm px-space-sm py-space-xs text-size-xs rounded font-mono">
          (Total Time &minus; Downtime) / Total Time &times; 100
        </p>
        <p className="text-content-secondary mb-space-sm">
          Only <strong>T0 service tier</strong> incidents with{' '}
          <strong>availability impact</strong> are included.
        </p>
        <p className="text-content-secondary mb-space-md">
          Downtime is captured in the time period the incident was created.
        </p>
        <h4 className="text-content-headings mb-space-xs font-medium">
          Color thresholds
        </h4>
        <ul className="text-content-secondary space-y-space-xs">
          <li className="gap-space-xs flex items-center">
            <span className="bg-graphics-success-moderate inline-block size-3 rounded" />
            <span>Green: &ge; 99.9%</span>
          </li>
          <li className="gap-space-xs flex items-center">
            <span className="bg-graphics-warning-moderate inline-block size-3 rounded" />
            <span>Yellow: &ge; 99.85%</span>
          </li>
          <li className="gap-space-xs flex items-center">
            <span className="bg-graphics-danger-moderate inline-block size-3 rounded" />
            <span>Red: &lt; 99.85%</span>
          </li>
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
