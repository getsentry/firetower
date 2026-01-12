import {useState} from 'react';
import {setHours, setMinutes} from 'date-fns';
import {ChevronDownIcon, X} from 'lucide-react';

import {Button} from './Button';
import {Calendar} from './Calendar';
import {Input} from './Input';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

export interface DateTimePickerProps {
  value: Date | undefined;
  onChange: (date: Date | undefined) => void;
  defaultDate?: Date;
  isPlaceholderTime?: boolean;
}

export function DateTimePicker({
  value,
  onChange,
  defaultDate,
  isPlaceholderTime,
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);

  const timeValue =
    value && !isPlaceholderTime
      ? `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}`
      : '';

  return (
    <div className="flex items-center gap-space-sm">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="secondary" className="w-28 justify-between font-normal">
            {value ? value.toLocaleDateString() : 'Pick date'}
            <ChevronDownIcon className="h-4 w-4 shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto overflow-hidden p-0" align="start">
          <Calendar
            mode="single"
            selected={value}
            defaultMonth={value ?? defaultDate}
            captionLayout="dropdown"
            showOutsideDays={false}
            onSelect={date => {
              if (date && value) {
                date = setHours(date, value.getHours());
                date = setMinutes(date, value.getMinutes());
              }
              onChange(date);
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      <Input
        type="time"
        value={timeValue}
        disabled={!value}
        onChange={e => {
          if (!value) return;
          const [hours, minutes] = e.target.value.split(':').map(Number);
          if (!isNaN(hours) && !isNaN(minutes)) {
            const newDate = new Date(value);
            newDate.setHours(hours);
            newDate.setMinutes(minutes);
            newDate.setSeconds(0);
            onChange(newDate);
          }
        }}
        className="bg-background text-size-md w-16 px-2 appearance-none disabled:opacity-30 [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
      />
      <Button
        variant="icon"
        onClick={() => onChange(undefined)}
        disabled={!value}
        aria-label="Clear date and time"
        className="disabled:cursor-default disabled:hover:bg-transparent disabled:hover:text-content-secondary"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
