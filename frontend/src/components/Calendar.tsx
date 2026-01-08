import {DayPicker, type DayPickerProps} from 'react-day-picker';
import {ChevronLeft, ChevronRight} from 'lucide-react';
import {cn} from 'utils/cn';

import {Button} from './Button';

export type CalendarProps = DayPickerProps;

function Calendar({className, classNames, ...props}: CalendarProps) {
  return (
    <DayPicker
      className={cn('p-space-md', className)}
      classNames={{
        months: 'flex flex-col sm:flex-row gap-space-md',
        month: 'flex flex-col gap-space-md',
        month_caption: 'flex justify-center pt-space-xs relative items-center',
        caption_label: 'text-size-sm font-medium',
        nav: 'flex items-center gap-space-xs',
        button_previous: 'absolute left-0',
        button_next: 'absolute right-0',
        month_grid: 'w-full border-collapse',
        weekdays: 'flex',
        weekday: 'text-content-secondary rounded-radius-md w-8 font-normal text-size-xs',
        week: 'flex w-full mt-space-xs',
        day: cn(
          'relative p-0 text-center text-size-sm',
          'focus-within:relative focus-within:z-20',
          '[&:has([aria-selected])]:bg-background-accent-vibrant',
          '[&:has([aria-selected])]:rounded-radius-md'
        ),
        day_button: cn(
          'h-8 w-8 p-0 font-normal rounded-radius-md',
          'hover:bg-background-transparent-neutral-muted',
          'focus:outline-auto',
          'aria-selected:bg-background-accent-vibrant aria-selected:text-content-on-vibrant-light',
          'aria-selected:hover:bg-background-accent-vibrant'
        ),
        range_start: 'rounded-l-radius-md',
        range_end: 'rounded-r-radius-md',
        selected:
          'bg-background-accent-vibrant text-content-on-vibrant-light rounded-radius-md',
        today: 'bg-background-secondary rounded-radius-md',
        outside: 'text-content-disabled opacity-50',
        disabled: 'text-content-disabled opacity-50',
        hidden: 'invisible',
        ...classNames,
      }}
      components={{
        Chevron: ({orientation}) =>
          orientation === 'left' ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          ),
        PreviousMonthButton: ({className, ...props}) => (
          <Button
            variant="icon"
            className={className}
            {...props}
            aria-label="Previous month"
          />
        ),
        NextMonthButton: ({className, ...props}) => (
          <Button
            variant="icon"
            className={className}
            {...props}
            aria-label="Next month"
          />
        ),
      }}
      {...props}
    />
  );
}

export {Calendar};
