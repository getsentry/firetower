import * as stylex from '@stylexjs/stylex';

import {content, fontSize, space} from '../../../styles/tokens.stylex';
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
    <div {...stylex.props(styles.container)}>
      <div {...stylex.props(styles.regionSpacer)} aria-hidden />
      <div {...stylex.props(styles.periods)}>
        {labels.map((p, i) => {
          const isCurrent = i === labels.length - 1;
          return (
            <div key={p.start} {...stylex.props(styles.period)}>
              <span
                {...stylex.props(
                  styles.label,
                  isCurrent ? styles.current : styles.previous
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

const styles = stylex.create({
  container: {
    marginBottom: space.sm,
    gap: space.lg,
    paddingInline: space.xl,
    display: 'flex',
    alignItems: 'center',
  },
  regionSpacer: {width: 128, flexShrink: 0},
  periods: {display: 'flex', minWidth: 0, flex: '1 1 0%', gap: 1},
  period: {minWidth: 0, flex: '1 1 0%', textAlign: 'center'},
  label: {fontSize: fontSize.xs},
  current: {color: content.headings, fontWeight: 600},
  previous: {color: content.secondary, fontWeight: 400},
});
