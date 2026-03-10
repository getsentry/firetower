import {type PeriodData} from '../queries/availabilityQueryOptions';

import {HeatmapBar} from './HeatmapBar';

interface RegionRowProps {
  regionName: string;
  periods: PeriodData[];
}

export function RegionRow({regionName, periods}: RegionRowProps) {
  const heatmapBlocks = [...periods].reverse().map(p => {
    const region = p.regions.find(r => r.name === regionName);
    return {
      availability: region?.availability_percentage ?? 100,
      periodStart: p.start,
      periodEnd: p.end,
      regionName,
    };
  });

  return (
    <div className="gap-space-lg flex items-center">
      <span className="text-content-headings text-size-md w-32 shrink-0 truncate font-medium">
        {regionName}
      </span>
      <HeatmapBar blocks={heatmapBlocks} />
    </div>
  );
}
