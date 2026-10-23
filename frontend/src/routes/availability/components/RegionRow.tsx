import * as stylex from '@stylexjs/stylex';

import {content, fontSize, fontWeight, space} from '../../../styles/tokens.stylex';
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
    <div {...stylex.props(styles.row)}>
      <span {...stylex.props(styles.label)}>{regionName}</span>
      <HeatmapBar blocks={heatmapBlocks} />
    </div>
  );
}

const styles = stylex.create({
  row: {gap: space.lg, display: 'flex', alignItems: 'center'},
  label: {
    color: content.headings,
    fontSize: fontSize.md,
    width: 128,
    flexShrink: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontWeight: fontWeight.medium,
  },
});
