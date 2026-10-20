import {useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {ChevronDownIcon, X} from 'lucide-react';

import {background, content, fontSize, space} from '../styles/tokens.stylex';

import {Button} from './Button';
import {buttonStyles} from './buttonStyles';
import {Calendar} from './Calendar';
import {Input} from './Input';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

export interface DateTimePickerProps {
  date: Date | undefined;
  time: string | undefined; // "HH:MM" format
  onDateChange: (date: Date | undefined) => void;
  onTimeChange: (time: string | undefined) => void;
  defaultDate?: Date;
}

export function DateTimePicker({
  date,
  time,
  onDateChange,
  onTimeChange,
  defaultDate,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div {...stylex.props(styles.row)}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            {...stylex.props(buttonStyles({variant: 'secondary'}), styles.dateTrigger)}
          >
            {date ? date.toLocaleDateString() : 'Pick date'}
            <ChevronDownIcon {...stylex.props(styles.chevron)} />
          </button>
        </PopoverTrigger>
        <PopoverContent style={styles.popover} align="start">
          <Calendar
            mode="single"
            selected={date}
            defaultMonth={date ?? defaultDate}
            captionLayout="dropdown"
            showOutsideDays={false}
            onSelect={newDate => {
              onDateChange(newDate);
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      <Input
        type="time"
        value={time ?? ''}
        disabled={!date}
        onChange={e => {
          onTimeChange(e.target.value || undefined);
        }}
        style={styles.timeInput}
      />
      <Button
        variant="icon"
        onClick={() => {
          onDateChange(undefined);
          onTimeChange(undefined);
        }}
        disabled={!date}
        aria-label="Clear date and time"
        style={styles.clearButton}
      >
        <X {...stylex.props(styles.icon)} />
      </Button>
    </div>
  );
}

const styles = stylex.create({
  row: {gap: space.sm, display: 'flex', alignItems: 'center'},
  dateTrigger: {width: 112, justifyContent: 'space-between', fontWeight: 400},
  chevron: {height: 16, width: 16, flexShrink: 0},
  popover: {width: 'auto', overflow: 'hidden', padding: 0},
  timeInput: {
    backgroundColor: background.primary,
    fontSize: fontSize.md,
    width: '85px',
    appearance: {default: 'none', '::-webkit-calendar-picker-indicator': 'none'},
    paddingInline: 8,
    opacity: {default: null, ':disabled': 0.3},
    display: {default: null, '::-webkit-calendar-picker-indicator': 'none'},
  },
  clearButton: {
    color: {
      default: content.secondary,
      ':disabled': {default: content.secondary, ':hover': content.secondary},
    },
    cursor: {default: 'pointer', ':disabled': 'default'},
    backgroundColor: {
      default: 'transparent',
      ':disabled': {default: 'transparent', ':hover': 'transparent'},
    },
  },
  icon: {height: 16, width: 16},
});
