import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {z} from 'zod';

import {availabilityQueryOptions} from './queries/availabilityQueryOptions';
import {PeriodTab} from './components/PeriodTab';
import {RegionTable} from './components/RegionTable';

// ─── Types ────────────────────────────────────────────────────────────────────

const PeriodSchema = z.enum(['month', 'quarter', 'year']);

const availabilitySearchSchema = z.object({
  period: PeriodSchema.optional(),
  subperiod: z.number().int().min(0).optional(),
});

// ─── Route ────────────────────────────────────────────────────────────────────

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

// ─── Page ─────────────────────────────────────────────────────────────────────

function AvailabilityPage() {
  const {period = 'month', subperiod = 0} = Route.useSearch();
  const {data} = useSuspenseQuery(availabilityQueryOptions());

  const periodsKey =
    period === 'month' ? 'months' : period === 'quarter' ? 'quarters' : 'years';
  const periods = data[periodsKey];
  const selectedIndex = Math.min(subperiod, periods.length - 1);

  const oldestLabel = periods.length > 1 ? periods[periods.length - 1].label : null;
  const newestLabel = periods[0]?.label ?? '';
  const rangeLabel = oldestLabel ? `${oldestLabel} – ${newestLabel}` : newestLabel;

  return (
    <div className="flex flex-col gap-space-xl">
      <div>
        <h1 className="mb-space-xs text-2xl font-semibold text-content-headings">
          Availability by Region
        </h1>
        <p className="text-content-secondary text-size-sm">{rangeLabel}</p>
      </div>

      <div className="flex gap-space-2xs">
        <PeriodTab period="month" label="Month" isActive={period === 'month'} />
        <PeriodTab period="quarter" label="Quarter" isActive={period === 'quarter'} />
        <PeriodTab period="year" label="Year" isActive={period === 'year'} />
      </div>

      <Card>
        <RegionTable
          periods={periods}
          selectedIndex={selectedIndex}
          activePeriod={period}
          key={period}
        />
      </Card>
    </div>
  );
}
