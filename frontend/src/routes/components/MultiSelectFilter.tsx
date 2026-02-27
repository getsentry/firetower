import {useState} from 'react';
import {Button} from 'components/Button';
import {Input} from 'components/Input';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {CheckIcon, ChevronDownIcon} from 'lucide-react';
import {cn} from 'utils/cn';

interface MultiSelectFilterProps {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (value: string) => void;
  renderOption?: (value: string) => React.ReactNode;
  searchable?: boolean;
}

export function MultiSelectFilter({
  label,
  options,
  selected,
  onToggle,
  renderOption,
  searchable = false,
}: MultiSelectFilterProps) {
  const [search, setSearch] = useState('');

  const filtered = searchable
    ? options.filter(o => o.toLowerCase().includes(search.toLowerCase()))
    : options;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm">
          {label}
          {selected.length > 0 && (
            <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
              {selected.length}
            </span>
          )}
          <ChevronDownIcon className="ml-space-2xs h-3.5 w-3.5 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-52 p-0">
        {searchable && (
          <div className="p-space-sm pb-0">
            <Input
              placeholder={`Filter ${label.toLowerCase()}...`}
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        )}
        <ul className="max-h-60 overflow-y-auto p-1" role="listbox" aria-label={label}>
          {filtered.map(option => {
            const isSelected = selected.includes(option);
            return (
              <li
                key={option}
                role="option"
                aria-selected={isSelected}
                className={cn(
                  'flex cursor-pointer items-center gap-2 rounded-radius-sm px-2 py-1.5 text-size-sm',
                  'hover:bg-background-transparent-neutral-muted'
                )}
                onClick={() => onToggle(option)}
              >
                <span
                  className={cn(
                    'flex h-4 w-4 shrink-0 items-center justify-center rounded-radius-xs border',
                    isSelected
                      ? 'border-accent-vibrant bg-background-accent-vibrant text-content-on-vibrant-light'
                      : 'border-gray-200'
                  )}
                >
                  {isSelected && <CheckIcon className="h-3 w-3" />}
                </span>
                {renderOption ? renderOption(option) : option}
              </li>
            );
          })}
          {filtered.length === 0 && (
            <li className="text-content-secondary px-2 py-1.5 text-size-sm">
              No results
            </li>
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
