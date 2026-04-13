import {cn} from 'utils/cn';

import {type PeriodData} from '../queries/availabilityQueryOptions';

interface PeriodLabelsProps {
  periods: PeriodData[];
}

function abbreviateLabel(label: string): string {
  return label.replace(
    /^(January|February|March|April|May|June|July|August|September|October|November|December)/,
    m => m.slice(0, 3)
  );
}

export function PeriodLabels({periods}: PeriodLabelsProps) {
  const labels = [...periods].reverse();

  return (
    <div className="mb-space-sm gap-space-lg flex items-center px-space-xl">
      <div className="w-32 shrink-0" aria-hidden />
      <div className="flex min-w-0 flex-1 gap-px">
        {labels.map((p, i) => {
          const isCurrent = i === labels.length - 1;
          return (
            <div key={p.start} className="min-w-0 flex-1 text-center">
              <span
                className={cn(
                  'text-size-xs',
                  isCurrent
                    ? 'text-content-headings font-semibold'
                    : 'text-content-secondary font-normal'
                )}
              >
                {abbreviateLabel(p.label)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
