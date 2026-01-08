import {useCallback} from 'react';
import {format, setHours, setMinutes} from 'date-fns';
import {Calendar as CalendarIcon, Clock} from 'lucide-react';
import {cn} from 'utils/cn';

import {Button} from './Button';
import {Calendar} from './Calendar';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

export interface DateTimePickerProps {
  value: Date | null;
  onChange: (date: Date | null) => void;
  datePlaceholder?: string;
  className?: string;
}

export function DateTimePicker({
  value,
  onChange,
  datePlaceholder = 'Pick a date',
  className,
}: DateTimePickerProps) {
  const handleDateSelect = useCallback(
    (date: Date | undefined) => {
      if (!date) {
        onChange(null);
        return;
      }

      if (value) {
        date = setHours(date, value.getHours());
        date = setMinutes(date, value.getMinutes());
      }
      onChange(date);
    },
    [value, onChange]
  );

  const handleTimeSelect = useCallback(
    (hours: number, minutes: number) => {
      const newDate = value ? new Date(value) : new Date();
      onChange(setMinutes(setHours(newDate, hours), minutes));
    },
    [value, onChange]
  );

  const timeValue = value
    ? `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
    : '';

  return (
    <div className={cn('flex gap-space-sm', className)}>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="secondary"
            className={cn(
              'h-auto w-auto justify-start gap-space-sm px-space-md py-space-sm font-normal',
              !value && 'text-content-disabled'
            )}
          >
            <CalendarIcon className="h-4 w-4" />
            {value ? format(value, 'PPP') : datePlaceholder}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto p-0">
          <Calendar
            mode="single"
            selected={value ?? undefined}
            onSelect={handleDateSelect}
          />
        </PopoverContent>
      </Popover>

      <div
        className={cn(
          'flex items-center gap-space-sm rounded-radius-md border border-gray-200 bg-white px-space-md py-space-sm',
          'focus-within:border-accent-moderate'
        )}
      >
        <Clock className="h-4 w-4 text-content-secondary" />
        <input
          type="time"
          value={timeValue}
          onChange={e => {
            const [hours, minutes] = e.target.value.split(':').map(Number);
            if (!isNaN(hours) && !isNaN(minutes)) {
              handleTimeSelect(hours, minutes);
            }
          }}
          className="bg-transparent text-size-sm focus:outline-none [&::-webkit-calendar-picker-indicator]:hidden"
        />
      </div>
    </div>
  );
}
