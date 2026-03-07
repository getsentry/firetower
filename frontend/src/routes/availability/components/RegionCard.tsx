import {Card} from 'components/Card';

import {type PeriodData} from '../queries/availabilityQueryOptions';

import {HeatmapBar} from './HeatmapBar';

interface RegionCardProps {
  regionName: string;
  periods: PeriodData[];
  showPeriodLabels?: boolean;
}

export function RegionCard({regionName, periods, showPeriodLabels}: RegionCardProps) {
  const heatmapBlocks = [...periods].reverse().map(p => {
    const region = p.regions.find(r => r.name === regionName);
    return {
      label: p.label,
      availability: region?.availability_percentage ?? 100,
      periodStart: p.start,
      periodEnd: p.end,
      regionName,
    };
  });

  return (
    <Card className="p-0">
      <div className="flex flex-col gap-3 px-space-xl pt-3 pb-6">
        <span className="text-content-headings text-size-lg font-semibold">
          {regionName}
        </span>
        <HeatmapBar blocks={heatmapBlocks} showEndLabels={showPeriodLabels} />
      </div>
    </Card>
  );
}
