import {Fragment} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {z} from 'zod';

import {background, content, fontSize, radius, space} from '../../styles/tokens.stylex';

import {AvailabilityTooltip} from './components/AvailabilityTooltip';
import {PeriodLabels} from './components/PeriodLabels';
import {PeriodTabs} from './components/PeriodTabs';
import {RegionRow} from './components/RegionRow';
import {
  availabilityQueryOptions,
  PeriodSchema,
  type AvailabilityData,
  type Period,
  type PeriodData,
} from './queries/availabilityQueryOptions';

const availabilitySearchSchema = z.object({
  period: PeriodSchema.optional(),
});

export const Route = createFileRoute('/availability/')({
  component: AvailabilityPage,
  validateSearch: zodValidator(availabilitySearchSchema),
  loader: async ({context}) => {
    await context.queryClient.ensureQueryData(availabilityQueryOptions());
  },
  errorComponent: () => (
    <ErrorState
      title="Something went wrong fetching availability data"
      description={
        <>
          Try refreshing the page, or if that doesn't work, come chat with us in{' '}
          <GetHelpLink />.
        </>
      }
    />
  ),
});

function getPeriodsForGranularity(data: AvailabilityData, period: Period): PeriodData[] {
  switch (period) {
    case 'month':
      return data.months;
    case 'quarter':
      return data.quarters;
    case 'year':
      return data.years;
  }
}

function getDateRangeLabel(periods: PeriodData[]): string {
  if (periods.length === 0) return '';
  const newest = periods[0];
  const oldest = periods[periods.length - 1];
  return `${oldest.label} – ${newest.label}`;
}

function AvailabilityPage() {
  const {period: periodParam} = Route.useSearch();
  const activePeriod: Period = periodParam ?? 'month';
  const {data} = useSuspenseQuery(availabilityQueryOptions());

  const periods = getPeriodsForGranularity(data, activePeriod);
  const currentPeriod = periods[0];
  const regions = currentPeriod?.regions ?? [];

  return (
    <div {...stylex.props(styles.page)}>
      <div {...stylex.props(styles.header)}>
        <div>
          <div {...stylex.props(styles.titleRow)}>
            <h1 {...stylex.props(styles.title)}>Availability by Region</h1>
            <AvailabilityTooltip />
          </div>
          <p {...stylex.props(styles.dateRange)}>{getDateRangeLabel(periods)}</p>
        </div>
        <PeriodTabs activePeriod={activePeriod} />
      </div>
      <PeriodLabels periods={periods} />
      <div {...stylex.props(styles.regions)}>
        {regions.map((region, i) => {
          const showGroupSpacing =
            i > 0 && region.group_index !== regions[i - 1]!.group_index;
          return (
            <Fragment key={region.name}>
              {showGroupSpacing ? (
                <div {...stylex.props(styles.groupSpacer)} aria-hidden />
              ) : null}
              <RegionRow regionName={region.name} periods={periods} />
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

const styles = stylex.create({
  page: {display: 'flex', flexDirection: 'column'},
  header: {
    marginBottom: space.xl,
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: 16,
  },
  titleRow: {gap: space.sm, display: 'flex', alignItems: 'center'},
  title: {color: content.headings, fontSize: fontSize['2xl'], fontWeight: 600},
  dateRange: {color: content.secondary, marginTop: space.xs, fontSize: fontSize.sm},
  regions: {
    backgroundColor: background.primary,
    borderRadius: radius.lg,
    padding: space['2xl'],
    gap: space.md,
    paddingInline: space.xl,
    paddingTop: space['2xl'],
    paddingBottom: space['2xl'],
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  groupSpacer: {paddingTop: space.md},
});
