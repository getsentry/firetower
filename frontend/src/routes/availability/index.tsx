import {useState} from 'react';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute, Link} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import {cn} from 'utils/cn';
import {z} from 'zod';

import {
  availabilityQueryOptions,
  type PeriodData,
  type RegionAvailability,
} from './queries/availabilityQueryOptions';

// ─── Types ────────────────────────────────────────────────────────────────────

const PeriodSchema = z.enum(['month', 'quarter', 'year']);
type Period = z.infer<typeof PeriodSchema>;

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatAvailability(pct: number): string {
  if (pct >= 100) return '100%';
  return pct.toFixed(2) + '%';
}

function availabilityBgClass(pct: number): string {
  if (pct >= 99.9) return 'bg-avail-good';
  if (pct >= 99.85) return 'bg-avail-warn';
  return 'bg-avail-bad';
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface PeriodTabProps {
  period: Period;
  label: string;
  isActive: boolean;
}

function PeriodTab({period, label, isActive}: PeriodTabProps) {
  return (
    <Link
      to="/availability"
      search={{period}}
      preload="intent"
      aria-selected={isActive}
      className={cn(
        'rounded-radius-sm px-space-lg py-space-sm text-size-sm font-medium transition-colors',
        {
          'bg-background-primary text-content-headings shadow-sm': isActive,
          'text-content-secondary hover:text-black': !isActive,
        }
      )}
    >
      {label}
    </Link>
  );
}

interface AvailabilityCellProps {
  data: RegionAvailability;
  showIncidents: boolean;
}

function AvailabilityCell({data, showIncidents}: AvailabilityCellProps) {
  const pct = data.availability_percentage;
  return (
    <div className="space-y-0.5">
      <div className="text-lg tabular-nums text-content-headings">
        {formatAvailability(pct)}
      </div>
      <div className="text-xs text-content-secondary tabular-nums">
        {data.total_downtime_display ?? '—'}
        {data.incident_count > 0 && (
          <>
            {' '}
            · {data.incident_count} {data.incident_count === 1 ? 'incident' : 'incidents'}
          </>
        )}
      </div>
      {showIncidents && data.incidents.length > 0 && (
        <div className="mt-space-xs space-y-0.5 border-t border-secondary pt-1">
          {data.incidents.map(incident => (
            <div
              key={incident.id}
              title={`INC-${incident.id} · ${incident.title} · ${incident.total_downtime_display ?? '—'}`}
              className="flex items-baseline gap-space-xs"
            >
              <Link
                to="/$incidentId"
                params={{incidentId: `INC-${incident.id}`}}
                className="text-xs text-content-accent hover:underline font-medium shrink-0"
              >
                INC-{incident.id}
              </Link>
              <span className="text-xs text-content-secondary tabular-nums shrink-0 ml-auto">
                {incident.total_downtime_display ?? '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface RegionTableProps {
  periods: PeriodData[];
  selectedIndex: number;
  activePeriod: Period;
}

const MAX_VISIBLE_COLS = 6;

function RegionTable({periods, selectedIndex, activePeriod}: RegionTableProps) {
  const [showIncidents, setShowIncidents] = useState(false);
  const [windowStart, setWindowStart] = useState(0);

  const visiblePeriods = periods.slice(windowStart, windowStart + MAX_VISIBLE_COLS);
  const canGoBack = windowStart > 0;
  const canGoForward = windowStart + MAX_VISIBLE_COLS < periods.length;

  if (!periods.length || !periods[0].regions.length) {
    return (
      <div className="text-content-secondary py-space-4xl text-center">
        <p>No regions configured yet.</p>
      </div>
    );
  }

  // Build a lookup: periodIndex -> regionName -> RegionAvailability (full array for sorting)
  const byPeriod = periods.map(p => Object.fromEntries(p.regions.map(r => [r.name, r])));

  // Use the first period's region list as canonical (all periods have the same regions)
  const regionNames = periods[0].regions.map(r => r.name);

  // Sort by selected period's availability descending (best first), then alphabetically
  const sortedNames = [...regionNames].sort((a, b) => {
    const aPct = byPeriod[selectedIndex]?.[a]?.availability_percentage ?? 100;
    const bPct = byPeriod[selectedIndex]?.[b]?.availability_percentage ?? 100;
    if (aPct !== bPct) return bPct - aPct;
    return a.localeCompare(b);
  });

  const navButtonClass = cn(
    'flex items-center justify-center rounded-radius-sm p-space-xs transition-colors',
    'text-content-secondary hover:text-content-primary hover:bg-background-secondary'
  );

  return (
    <div>
      <div className="flex items-center justify-end gap-space-xs pb-space-sm px-space-sm">
        <button
          onClick={() => setWindowStart(w => w - 1)}
          disabled={!canGoBack}
          aria-label="Show newer periods"
          className={cn(navButtonClass, !canGoBack && 'invisible')}
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onClick={() => setWindowStart(w => w + 1)}
          disabled={!canGoForward}
          aria-label="Show older periods"
          className={cn(navButtonClass, !canGoForward && 'invisible')}
        >
          <ChevronRight size={16} />
        </button>
        <button
          onClick={() => setShowIncidents(v => !v)}
          className={cn(
            'rounded-radius-sm px-space-md py-space-xs text-size-sm font-medium transition-colors',
            showIncidents
              ? 'bg-background-accent-vibrant text-content-on-vibrant-light'
              : 'bg-background-secondary text-content-secondary hover:text-content-primary'
          )}
        >
          {showIncidents ? 'Hide incidents' : 'Show incidents'}
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-left">
          <colgroup>
            <col className="w-32" />
            {visiblePeriods.map((_, i) => (
              <col key={i} />
            ))}
          </colgroup>
          <thead>
            <tr className="border-secondary border-b">
              <th className="px-space-sm py-space-sm text-size-sm font-medium text-content-secondary">
                Region
              </th>
              {visiblePeriods.map((p, i) => {
                const globalIndex = windowStart + i;
                return (
                  <th
                    key={p.label}
                    className="px-space-sm py-space-sm text-size-sm font-medium"
                  >
                    <Link
                      to="/availability"
                      search={{period: activePeriod, subperiod: globalIndex}}
                      preload="intent"
                      className={cn(
                        'inline-block rounded-radius-sm px-space-sm py-space-xs transition-colors no-underline',
                        globalIndex === selectedIndex
                          ? 'bg-background-secondary text-content-headings'
                          : 'text-content-secondary hover:text-content-primary'
                      )}
                    >
                      {p.label}
                    </Link>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sortedNames.map(name => (
              <tr key={name} className="border-secondary border-b">
                <td className="align-top px-space-sm py-space-sm text-lg text-content-headings">
                  {name}
                </td>
                {visiblePeriods.map((_, i) => {
                  const globalIndex = windowStart + i;
                  const d = byPeriod[globalIndex]?.[name];
                  return (
                    <td
                      key={globalIndex}
                      className={cn(
                        'py-space-sm px-space-sm align-top',
                        d ? availabilityBgClass(d.availability_percentage) : ''
                      )}
                    >
                      {d ? (
                        <AvailabilityCell data={d} showIncidents={showIncidents} />
                      ) : (
                        <span className="text-content-secondary">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

function AvailabilityPage() {
  const {period = 'month', subperiod = 0} = Route.useSearch();
  const {data} = useSuspenseQuery(availabilityQueryOptions());

  const periodsKey =
    period === 'month' ? 'months' : period === 'quarter' ? 'quarters' : 'years';
  const periods = data[periodsKey];
  const selectedIndex = Math.min(subperiod, periods.length - 1);

  // Date range label spanning all loaded periods (oldest → newest)
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
