import {useState} from 'react';
import {Link} from '@tanstack/react-router';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import {cn} from 'utils/cn';

import type {Period, PeriodData} from '../queries/availabilityQueryOptions';
import {AvailabilityCell} from './AvailabilityCell';

function availabilityBgClass(pct: number): string {
  if (pct >= 99.9) return 'bg-avail-good';
  if (pct >= 99.85) return 'bg-avail-warn';
  return 'bg-avail-bad';
}

const MAX_VISIBLE_COLS = 6;

interface RegionTableProps {
  periods: PeriodData[];
  selectedIndex: number;
  activePeriod: Period;
}

export function RegionTable({periods, selectedIndex, activePeriod}: RegionTableProps) {
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

  const byPeriod = periods.map(p => Object.fromEntries(p.regions.map(r => [r.name, r])));
  const regionNames = periods[0].regions.map(r => r.name);

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
