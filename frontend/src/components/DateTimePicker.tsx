import {useState} from 'react';
import {setHours, setMinutes, setSeconds} from 'date-fns';
import {ChevronDownIcon} from 'lucide-react';

import {Button} from './Button';
import {Calendar} from './Calendar';
import {Input} from './Input';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

export interface DateTimePickerProps {
  value: Date | undefined;
  onChange: (date: Date | undefined) => void;
}

export function DateTimePicker({value, onChange}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);

  const timeValue = value
    ? `${String(value.getHours()).padStart(2, '0')}:${String(value.getMinutes()).padStart(2, '0')}:${String(value.getSeconds()).padStart(2, '0')}`
    : '';

  return (
    <div className="flex gap-4">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="secondary" className="w-32 justify-between font-normal">
            {value ? value.toLocaleDateString() : 'Select date'}
            <ChevronDownIcon />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto overflow-hidden p-0" align="start">
          <Calendar
            mode="single"
            selected={value}
            defaultMonth={value}
            captionLayout="dropdown"
            showOutsideDays={false}
            onSelect={date => {
              if (date && value) {
                date = setHours(date, value.getHours());
                date = setMinutes(date, value.getMinutes());
                date = setSeconds(date, value.getSeconds());
              }
              onChange(date);
              setOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
      <Input
        type="time"
        step="1"
        value={timeValue}
        disabled={!value}
        onChange={e => {
          if (!value) return;
          const [hours, minutes, seconds] = e.target.value.split(':').map(Number);
          if (!isNaN(hours) && !isNaN(minutes)) {
            const newDate = new Date(value);
            newDate.setHours(hours);
            newDate.setMinutes(minutes);
            newDate.setSeconds(seconds || 0);
            onChange(newDate);
          }
        }}
        className="bg-background text-size-md w-auto appearance-none [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
      />
    </div>
  );
}
