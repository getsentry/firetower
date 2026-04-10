import {useCallback, useRef, useState} from 'react';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {Info} from 'lucide-react';
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
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const closeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = useCallback(() => {
    if (closeTimeout.current) {
      clearTimeout(closeTimeout.current);
      closeTimeout.current = null;
    }
    setTooltipOpen(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    closeTimeout.current = setTimeout(() => {
      setTooltipOpen(false);
    }, 100);
  }, []);

  const periods = getPeriodsForGranularity(data, activePeriod);
  const currentPeriod = periods[0];
  const regionNames = currentPeriod?.regions.map(r => r.name) ?? [];

  return (
    <div className="flex flex-col">
      <div className="mb-space-xl flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="gap-space-sm flex items-center">
            <h1 className="text-content-headings text-size-2xl font-semibold">
              Availability by Region
            </h1>
            <Popover open={tooltipOpen} onOpenChange={setTooltipOpen}>
              <PopoverTrigger asChild>
                <button
                  className="text-content-secondary hover:text-content-primary transition-colors"
                  aria-label="How availability is calculated"
                  onMouseEnter={handleMouseEnter}
                  onMouseLeave={handleMouseLeave}
                >
                  <Info size={18} />
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="start"
                className="text-size-sm max-w-sm"
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
              >
                <h3 className="text-content-headings mb-space-sm font-semibold">
                  How availability is calculated
                </h3>
                <p className="text-content-secondary mb-space-sm">
                  Availability percentage is calculated as:
                </p>
                <p className="text-content-primary bg-background-secondary mb-space-sm px-space-sm py-space-xs text-size-xs rounded font-mono">
                  (Total Time − Downtime) / Total Time × 100
                </p>
                <p className="text-content-secondary mb-space-sm">
                  Only <strong>T0 service tier</strong> incidents with{' '}
                  <strong>availability impact</strong> are included.
                </p>
                <p className="text-content-secondary mb-space-md">
                  Downtime is captured in the month the incident was created.
                </p>
                <h4 className="text-content-headings mb-space-xs font-medium">
                  Color thresholds
                </h4>
                <ul className="text-content-secondary space-y-space-xs">
                  <li className="gap-space-xs flex items-center">
                    <span className="bg-graphics-success-moderate inline-block size-3 rounded" />
                    <span>Green: ≥ 99.9%</span>
                  </li>
                  <li className="gap-space-xs flex items-center">
                    <span className="bg-graphics-warning-moderate inline-block size-3 rounded" />
                    <span>Yellow: ≥ 99.85%</span>
                  </li>
                  <li className="gap-space-xs flex items-center">
                    <span className="bg-graphics-danger-moderate inline-block size-3 rounded" />
                    <span>Red: &lt; 99.85%</span>
                  </li>
                </ul>
              </PopoverContent>
            </Popover>
          </div>
          <p className="text-content-secondary mt-space-xs text-size-sm">
            {getDateRangeLabel(periods)}
          </p>
        </div>
        <PeriodTabs activePeriod={activePeriod} />
      </div>
      <Card className="gap-space-md px-space-xl pt-space-sm pb-space-lg flex flex-col">
        <PeriodLabels periods={periods} />
        {regionNames.map(name => (
          <RegionRow key={name} regionName={name} periods={periods} />
        ))}
      </Card>
    </div>
  );
}
