import * as stylex from '@stylexjs/stylex';
import {Link} from '@tanstack/react-router';

import {fontFamily, fontSize, fontWeight, graphics} from '../../../styles/tokens.stylex';
import {getAvailabilityLevel, type AvailabilityLevel} from '../utils';

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
    <div {...stylex.props(styles.bar)}>
      {blocks.map((block, i) => {
        const isFullUptime = block.availability >= 100;
        const displayPct = isFullUptime
          ? '100.00'
          : Math.min(99.99, block.availability).toFixed(2);
        const inner = (
          <div
            {...stylex.props(
              styles.cell,
              availabilityStyles[getAvailabilityLevel(block.availability)],
              i === 0 && styles.first,
              i === blocks.length - 1 && styles.last
            )}
          >
            <span {...stylex.props(styles.percentage)}>{displayPct}%</span>
          </div>
        );

        return isFullUptime ? (
          <div key={i} {...stylex.props(styles.block)}>
            {inner}
          </div>
        ) : (
          <Link
            key={i}
            {...stylex.props(styles.block, styles.link)}
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

const styles = stylex.create({
  bar: {display: 'flex', minWidth: 0, flex: '1 1 0%', gap: 1, overflow: 'visible'},
  block: {position: 'relative', minWidth: 0, flex: '1 1 0%'},
  link: {
    opacity: {default: 1, '@media (min-width: 640px)': {default: 1, ':hover': 0.8}},
    transitionProperty: {default: null, '@media (min-width: 640px)': 'opacity'},
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  cell: {display: 'flex', height: 32, alignItems: 'center', justifyContent: 'center'},
  first: {borderTopLeftRadius: 6, borderBottomLeftRadius: 6},
  last: {borderTopRightRadius: 6, borderBottomRightRadius: 6},
  percentage: {
    fontSize: fontSize.sm,
    fontFamily: fontFamily.mono,
    fontWeight: fontWeight.medium,
    color: '#fff',
    filter: 'drop-shadow(0 3px 3px rgb(0 0 0 / 0.12))',
    userSelect: 'none',
  },
  success: {backgroundColor: graphics.successModerate},
  warning: {backgroundColor: graphics.warningModerate},
  danger: {backgroundColor: graphics.dangerModerate},
});

const availabilityStyles: Record<AvailabilityLevel, stylex.StyleXStyles> = {
  success: styles.success,
  warning: styles.warning,
  danger: styles.danger,
};
