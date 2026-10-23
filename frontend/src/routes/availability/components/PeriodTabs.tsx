import * as stylex from '@stylexjs/stylex';
import {Link} from '@tanstack/react-router';

import {
  background,
  content,
  fontSize,
  fontWeight,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import {type Period} from '../queries/availabilityQueryOptions';

const TABS: {value: Period; label: string}[] = [
  {value: 'month', label: 'Month'},
  {value: 'quarter', label: 'Quarter'},
  {value: 'year', label: 'Year'},
];

interface PeriodTabsProps {
  activePeriod: Period;
}

export function PeriodTabs({activePeriod}: PeriodTabsProps) {
  return (
    <div {...stylex.props(styles.tabs)}>
      {TABS.map(tab => (
        <Link
          key={tab.value}
          to="/availability"
          search={{period: tab.value}}
          preload="intent"
          {...stylex.props(
            styles.tab,
            activePeriod === tab.value ? styles.active : styles.inactive
          )}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}

const styles = stylex.create({
  tabs: {gap: space['2xs'], display: 'flex'},
  tab: {
    borderRadius: radius.sm,
    paddingInline: space.lg,
    paddingBlock: space.sm,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  active: {
    backgroundColor: {
      default: background.primary,
      '@media (prefers-color-scheme: dark)': background.transparentNeutralMuted,
    },
    color: content.headings,
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  inactive: {
    color: {
      default: content.secondary,
      ':hover': '#000',
      '@media (prefers-color-scheme: dark)': {
        default: content.secondary,
        ':hover': '#fff',
      },
    },
  },
});
