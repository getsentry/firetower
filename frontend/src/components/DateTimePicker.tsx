import {useState} from 'react';
import {ChevronDownIcon, X} from 'lucide-react';

import {Button} from './Button';
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
    <div className="flex items-center gap-space-sm">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="secondary" className="w-28 justify-between font-normal">
            {date ? date.toLocaleDateString() : 'Pick date'}
            <ChevronDownIcon className="h-4 w-4 shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto overflow-hidden p-0" align="start">
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
        className="bg-background text-size-md w-16 px-2 appearance-none disabled:opacity-30 [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
      />
      <Button
        variant="icon"
        onClick={() => {
          onDateChange(undefined);
          onTimeChange(undefined);
        }}
        disabled={!date}
        aria-label="Clear date and time"
        className="disabled:cursor-default disabled:hover:bg-transparent disabled:hover:text-content-secondary"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
