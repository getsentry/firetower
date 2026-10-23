import * as stylex from '@stylexjs/stylex';
import {Link, useSearch} from '@tanstack/react-router';
import {arraysEqual} from 'utils/arrays';

import {
  background,
  content,
  fontSize,
  fontWeight,
  radius,
  space,
} from '../../styles/tokens.stylex';
import {STATUS_FILTER_GROUPS, type StatusFilterValue} from '../types';

interface FilterLinkProps {
  statuses?: StatusFilterValue[];
  label: string;
  isActive: boolean;
  testId?: string;
}

function FilterLink({statuses, label, isActive, testId}: FilterLinkProps) {
  return (
    <Link
      to="/"
      search={prev => ({...prev, status: statuses})}
      preload="intent"
      data-testid={testId}
      aria-selected={isActive}
      {...stylex.props(styles.tab, isActive ? styles.active : styles.inactive)}
    >
      {label}
    </Link>
  );
}

export function StatusFilter() {
  const {status} = useSearch({from: '/'});

  return (
    <div {...stylex.props(styles.tabs)}>
      <FilterLink
        statuses={undefined}
        label="Active"
        isActive={
          status === undefined || arraysEqual(status, STATUS_FILTER_GROUPS.active)
        }
        testId="filter-active"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.review}
        label="In Review"
        isActive={arraysEqual(status ?? [], STATUS_FILTER_GROUPS.review)}
        testId="filter-review"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.closed}
        label="Closed"
        isActive={arraysEqual(status ?? [], STATUS_FILTER_GROUPS.closed)}
        testId="filter-closed"
      />
      <FilterLink
        statuses={STATUS_FILTER_GROUPS.all}
        label="All"
        isActive={arraysEqual(status ?? [], STATUS_FILTER_GROUPS.all)}
        testId="filter-all"
      />
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
      ':hover': background.transparentNeutralMuted,
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
    backgroundColor: {default: null, ':hover': background.transparentNeutralMuted},
  },
});
