import {useState} from 'react';
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

export function DateRangeFilter() {
  const navigate = useNavigate();
  const {search} = useActiveFilters();
  const after = search.created_after as string | undefined;
  const before = search.created_before as string | undefined;
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
    <div className="col-span-1">
      <div className="mb-space-md">
        <h3 className="text-size-md text-content-secondary font-semibold">
          Created Date
        </h3>
      </div>
      <div className="gap-space-xs flex flex-wrap items-center">
        <Popover
          open={editing === 'after'}
          onOpenChange={o => setEditing(o ? 'after' : null)}
        >
          <PopoverTrigger asChild>
            {after ? (
              <Tag
                className="cursor-pointer select-none"
                action={
                  <Button
                    variant="close"
                    size={null}
                    onClick={e => {
                      e.stopPropagation();
                      update('created_after', undefined);
                    }}
                    aria-label="Clear start date"
                  >
                    <XIcon className="h-3.5 w-3.5" />
                  </Button>
                }
              >
                {formatDateDisplay(after)}
              </Tag>
            ) : (
              <button
                type="button"
                className="text-size-sm text-content-disabled cursor-pointer select-none italic"
              >
                Any
              </button>
            )}
          </PopoverTrigger>
          <PopoverContent className="w-auto overflow-hidden p-0" align="start">
            <Calendar
              mode="single"
              selected={afterDate}
              defaultMonth={afterDate}
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
            {before ? (
              <Tag
                className="cursor-pointer select-none"
                action={
                  <Button
                    variant="close"
                    size={null}
                    onClick={e => {
                      e.stopPropagation();
                      update('created_before', undefined);
                    }}
                    aria-label="Clear end date"
                  >
                    <XIcon className="h-3.5 w-3.5" />
                  </Button>
                }
              >
                {formatDateDisplay(before)}
              </Tag>
            ) : (
              <button
                type="button"
                className="text-size-sm text-content-disabled cursor-pointer select-none italic"
              >
                Any
              </button>
            )}
          </PopoverTrigger>
          <PopoverContent className="w-auto overflow-hidden p-0" align="start">
            <Calendar
              mode="single"
              selected={beforeDate}
              defaultMonth={beforeDate}
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
