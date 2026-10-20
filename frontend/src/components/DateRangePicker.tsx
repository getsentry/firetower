import {useRef} from 'react';
import type {DateRange} from 'react-day-picker';
import * as stylex from '@stylexjs/stylex';
import {XIcon} from 'lucide-react';

import {background, content, fontSize, radius, space} from '../styles/tokens.stylex';

import {Button} from './Button';
import {Calendar} from './Calendar';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

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
  const triggerRef = useRef<HTMLButtonElement>(null);
  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <span {...stylex.props(styles.control, value?.from && styles.selected)}>
        <PopoverTrigger asChild>
          <button
            ref={triggerRef}
            type="button"
            {...stylex.props(styles.trigger, !value?.from && styles.placeholder)}
          >
            {value?.from ? formatRange(value) : placeholder}
          </button>
        </PopoverTrigger>
        {value?.from && onClear && (
          <Button
            variant="close"
            size={null}
            onClick={() => {
              onClear();
              triggerRef.current?.focus();
            }}
            aria-label="Clear date range"
          >
            <XIcon {...stylex.props(styles.clearIcon)} />
          </Button>
        )}
      </span>
      <PopoverContent style={styles.popover} align={align}>
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

const styles = stylex.create({
  control: {display: 'inline-flex', alignItems: 'center', gap: space.xs},
  selected: {
    paddingInline: space.md,
    paddingBlock: space.xs,
    backgroundColor: {
      default: background.tertiary,
      '@media (prefers-color-scheme: dark)': {
        default: background.secondary,
        ':hover': background.transparentNeutralMuted,
      },
      ':hover': background.transparentNeutralMuted,
    },
    borderRadius: radius.xs,
    fontSize: fontSize.sm,
    color: content.secondary,
  },
  trigger: {cursor: 'pointer', userSelect: 'none', backgroundColor: 'transparent'},
  clearIcon: {height: 14, width: 14},
  placeholder: {fontSize: fontSize.sm, color: content.disabled, fontStyle: 'italic'},
  popover: {width: 'auto', overflow: 'hidden', padding: 0},
});
