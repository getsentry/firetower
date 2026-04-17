import {useState} from 'react';
import type {DateRange} from 'react-day-picker';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {DateRangePicker} from 'components/DateRangePicker';
import {Pencil} from 'lucide-react';

import {useActiveFilters} from '../useActiveFilters';

function toDateString(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function parseDate(dateStr: string | undefined): Date | undefined {
  if (!dateStr) return undefined;
  return new Date(dateStr + 'T00:00:00');
}

export function DateRangeFilter() {
  const navigate = useNavigate({from: '/'});
  const {search} = useActiveFilters();
  const [open, setOpen] = useState(false);
  const after = search.created_after;
  const before = search.created_before;

  const value: DateRange | undefined =
    after || before ? {from: parseDate(after), to: parseDate(before)} : undefined;

  const handleChange = (range: DateRange | undefined) => {
    navigate({
      to: '/',
      search: prev => ({
        ...prev,
        created_after: range?.from ? toDateString(range.from) : undefined,
        created_before: range?.to ? toDateString(range.to) : undefined,
      }),
      replace: true,
    });
  };

  const handleClear = () => {
    navigate({
      to: '/',
      search: prev => ({
        ...prev,
        created_after: undefined,
        created_before: undefined,
      }),
      replace: true,
    });
  };

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex min-h-[32px] items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">
          Created Date
        </h3>
        <Button
          variant="icon"
          onClick={() => setOpen(true)}
          aria-label="Edit date range"
          className={open ? 'invisible' : 'transition-none'}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex min-h-[28px] items-center">
        <DateRangePicker
          value={value}
          onChange={handleChange}
          onClear={handleClear}
          open={open}
          onOpenChange={setOpen}
          placeholder="Any"
        />
      </div>
    </div>
  );
}
