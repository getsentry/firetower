import React, {useState} from 'react';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Calendar} from 'components/Calendar';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {Tag} from 'components/Tag';
import {XIcon} from 'lucide-react';

import {useActiveFilters} from '../useActiveFilters';

function formatDateDisplay(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr.includes('T') ? dateStr : dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function toDateString(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function DateTrigger({
  value,
  clearLabel,
  onClear,
  ref,
  ...props
}: {
  value: string | undefined;
  clearLabel: string;
  onClear: () => void;
  ref?: React.Ref<HTMLElement>;
} & React.HTMLAttributes<HTMLElement>) {
  if (value) {
    return (
      <Tag
        ref={ref as React.Ref<HTMLSpanElement>}
        className="cursor-pointer select-none"
        action={
          <Button
            variant="close"
            size={null}
            onClick={e => {
              e.stopPropagation();
              onClear();
            }}
            aria-label={clearLabel}
          >
            <XIcon className="h-3.5 w-3.5" />
          </Button>
        }
        {...props}
      >
        {formatDateDisplay(value)}
      </Tag>
    );
  }

  return (
    <button
      ref={ref as React.Ref<HTMLButtonElement>}
      type="button"
      className="text-size-sm text-content-disabled cursor-pointer italic select-none"
      {...props}
    >
      Any
    </button>
  );
}

export function DateRangeFilter() {
  const navigate = useNavigate({from: '/'});
  const {search} = useActiveFilters();
  const after = search.created_after;
  const before = search.created_before;
  const [editing, setEditing] = useState<'after' | 'before' | null>(null);

  const afterDate = after ? new Date(after + 'T00:00:00') : undefined;
  const beforeDate = before ? new Date(before + 'T00:00:00') : undefined;

  const update = (key: 'created_after' | 'created_before', value: string | undefined) => {
    navigate({
      to: '/',
      search: prev => ({...prev, [key]: value}),
      replace: true,
    });
  };

  const handleDateSelect = (
    key: 'created_after' | 'created_before',
    date: Date | undefined
  ) => {
    update(key, date ? toDateString(date) : undefined);
    setEditing(null);
  };

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex min-h-[32px] items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">
          Created Date
        </h3>
      </div>
      <div className="gap-space-md flex min-h-[28px] flex-wrap items-center">
        <Popover
          open={editing === 'after'}
          onOpenChange={o => setEditing(o ? 'after' : null)}
        >
          <PopoverTrigger asChild>
            <DateTrigger
              value={after}
              clearLabel="Clear start date"
              onClear={() => update('created_after', undefined)}
            />
          </PopoverTrigger>
          <PopoverContent className="w-auto overflow-hidden p-0" align="start">
            <Calendar
              mode="single"
              selected={afterDate}
              defaultMonth={afterDate}
              disabled={beforeDate ? {after: beforeDate} : undefined}
              captionLayout="dropdown"
              showOutsideDays={false}
              onSelect={d => handleDateSelect('created_after', d)}
            />
          </PopoverContent>
        </Popover>
        <span className="text-content-disabled text-size-sm">to</span>
        <Popover
          open={editing === 'before'}
          onOpenChange={o => setEditing(o ? 'before' : null)}
        >
          <PopoverTrigger asChild>
            <DateTrigger
              value={before}
              clearLabel="Clear end date"
              onClear={() => update('created_before', undefined)}
            />
          </PopoverTrigger>
          <PopoverContent className="w-auto overflow-hidden p-0" align="start">
            <Calendar
              mode="single"
              selected={beforeDate}
              defaultMonth={beforeDate}
              disabled={afterDate ? {before: afterDate} : undefined}
              captionLayout="dropdown"
              showOutsideDays={false}
              onSelect={d => handleDateSelect('created_before', d)}
            />
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
}
