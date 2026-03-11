import React, {useRef, useState} from 'react';

import {Input} from './Input';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

interface MultiSelectProps<T extends string> {
  options: readonly T[];
  selected: T[];
  onToggle: (value: T) => void;
  renderOption: (value: T) => React.ReactNode;
  trigger: React.ReactNode;
  searchable?: boolean;
  searchPlaceholder?: string;
}

function MultiSelect<T extends string>({
  options,
  selected,
  onToggle,
  renderOption,
  trigger,
  searchable,
  searchPlaceholder = 'Search…',
}: MultiSelectProps<T>) {
  const [search, setSearch] = useState('');
  const listRef = useRef<HTMLUListElement>(null);

  const available = options.filter(o => !selected.includes(o));
  const filtered = searchable
    ? available.filter(o => o.toLowerCase().includes(search.toLowerCase()))
    : available;

  function handleKeyDown(e: React.KeyboardEvent) {
    const list = listRef.current;
    if (!list) return;

    const items = Array.from(list.querySelectorAll<HTMLLIElement>('[role="option"]'));
    const active = document.activeElement as HTMLElement;
    const idx = items.indexOf(active as HTMLLIElement);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = idx < items.length - 1 ? idx + 1 : 0;
      items[next]?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = idx > 0 ? idx - 1 : items.length - 1;
      items[prev]?.focus();
    }
  }

  return (
    <Popover onOpenChange={() => setSearch('')}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-fit p-space-xs"
        onKeyDown={handleKeyDown}
      >
        {searchable && (
          <div className="p-space-xs">
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={searchPlaceholder}
              autoFocus
            />
          </div>
        )}
        <ul
          ref={listRef}
          role="listbox"
          aria-multiselectable="true"
          className="flex flex-col"
        >
          {filtered.map(option => (
            <li
              key={option}
              role="option"
              aria-selected={false}
              tabIndex={-1}
              className="flex cursor-pointer items-center rounded-radius-sm px-space-sm py-space-xs hover:bg-background-transparent-neutral-muted"
              onClick={() => onToggle(option)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onToggle(option);
                }
              }}
            >
              {renderOption(option)}
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

export {MultiSelect, type MultiSelectProps};
