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
  const labels = [...periods].reverse().map(p => abbreviateLabel(p.label));

  return (
    <div className="gap-space-lg flex items-center">
      <div className="w-32 shrink-0" />
      <div className="flex min-w-0 flex-1 gap-px">
        {labels.map(label => (
          <div key={label} className="min-w-0 flex-1 text-center">
            <span className="text-content-secondary text-size-xs">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
