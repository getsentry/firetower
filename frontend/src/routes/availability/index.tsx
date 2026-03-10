import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {z} from 'zod';

import {PeriodLabels} from './components/PeriodLabels';
import {PeriodTabs} from './components/PeriodTabs';
import {RegionRow} from './components/RegionRow';
import {
  availabilityQueryOptions,
  PeriodSchema,
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

function getPeriodsForGranularity(
  data: {months: PeriodData[]; quarters: PeriodData[]; years: PeriodData[]},
  period: Period
): PeriodData[] {
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
  const regionNames = currentPeriod?.regions.map(r => r.name) ?? [];

  return (
    <div className="flex flex-col">
      <div className="mb-space-xl flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-content-headings text-size-2xl font-semibold">
            Availability by Region
          </h1>
          <p className="text-content-secondary mt-space-xs text-size-sm">
            {getDateRangeLabel(periods)}
          </p>
        </div>
        <PeriodTabs activePeriod={activePeriod} />
      </div>
      <Card className="flex flex-col gap-space-md px-space-xl pt-space-sm pb-space-lg">
        <PeriodLabels periods={periods} />
        {regionNames.map(name => (
          <RegionRow key={name} regionName={name} periods={periods} />
        ))}
      </Card>
    </div>
  );
}
