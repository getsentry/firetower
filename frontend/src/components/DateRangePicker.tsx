import type {DateRange} from 'react-day-picker';
import {XIcon} from 'lucide-react';

import {Button} from './Button';
import {Calendar} from './Calendar';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';
import {Tag} from './Tag';

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatRange(range: DateRange | undefined): string {
  if (!range?.from) return '';
  if (!range.to) return formatDate(range.from) + ' –';
  return formatDate(range.from) + ' – ' + formatDate(range.to);
}

interface DateRangePickerProps {
  value: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  onClear?: () => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  placeholder?: string;
  align?: 'start' | 'center' | 'end';
  numberOfMonths?: number;
}

export function DateRangePicker({
  value,
  onChange,
  onClear,
  open,
  onOpenChange,
  placeholder = 'Pick a date range',
  align = 'start',
  numberOfMonths = 2,
}: DateRangePickerProps) {
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        {value?.from ? (
          <Tag
            className="hover:bg-background-transparent-neutral-muted cursor-pointer select-none"
            action={
              onClear ? (
                <Button
                  variant="close"
                  size={null}
                  onClick={e => {
                    e.stopPropagation();
                    onClear();
                  }}
                  aria-label="Clear date range"
                >
                  <XIcon className="h-3.5 w-3.5" />
                </Button>
              ) : null
            }
          >
            {formatRange(value)}
          </Tag>
        ) : (
          <button
            type="button"
            className="text-size-sm text-content-disabled cursor-pointer italic select-none"
          >
            {placeholder}
          </button>
        )}
      </PopoverTrigger>
      <PopoverContent className="w-auto overflow-hidden p-0" align={align}>
        <Calendar
          mode="range"
          selected={value}
          onSelect={onChange}
          numberOfMonths={numberOfMonths}
          defaultMonth={value?.from}
          captionLayout="dropdown"
          showOutsideDays={false}
        />
      </PopoverContent>
    </Popover>
  );
}
