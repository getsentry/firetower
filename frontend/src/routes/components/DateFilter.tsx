import {Button} from 'components/Button';
import {Calendar} from 'components/Calendar';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {format, parseISO} from 'date-fns';
import {CalendarIcon, XIcon} from 'lucide-react';

interface DateFilterProps {
  label: string;
  value?: string;
  onChange: (value: string | undefined) => void;
}

export function DateFilter({label, value, onChange}: DateFilterProps) {
  const date = value ? parseISO(value) : undefined;

  return (
    <div className="flex items-center gap-space-2xs">
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="secondary" size="sm">
            <CalendarIcon className="h-3.5 w-3.5 opacity-50" />
            {date ? `${label}: ${format(date, 'MMM d, yyyy')}` : label}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-auto p-0">
          <Calendar
            mode="single"
            selected={date}
            onSelect={d => onChange(d ? format(d, 'yyyy-MM-dd') : undefined)}
          />
        </PopoverContent>
      </Popover>
      {value && (
        <button
          type="button"
          onClick={() => onChange(undefined)}
          className="text-content-secondary hover:text-content-primary cursor-pointer"
        >
          <XIcon className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
