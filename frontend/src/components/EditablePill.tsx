import {useCallback, useState} from 'react';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Pill, type PillProps} from './Pill';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';
import {Spinner} from './Spinner';

const optionRowStyles = cva(['group', 'w-fit', 'cursor-pointer', 'rounded-radius-full']);

const optionStyles = cva([
  'pointer-events-none',
  'transition-[filter]',
  'group-hover:brightness-90',
  'dark:group-hover:brightness-110',
]);

const triggerStyles = cva([
  'relative',
  'inline-flex',
  'cursor-pointer',
  'items-center',
  'rounded-radius-full',
  'leading-none',
  'select-none',
  'transition-all',
  'hover:scale-105',
  'hover:shadow-md',
  'active:scale-95',
]);

export interface EditablePillProps<T extends string> {
  value: T | null;
  options: readonly T[];
  onSave: (newValue: T) => Promise<void>;
  className?: string;
  getVariant?: (value: T) => PillProps['variant'];
  placeholder?: string;
}

export function EditablePill<T extends string>({
  value,
  options,
  onSave,
  className,
  getVariant,
  placeholder = 'Not set',
}: EditablePillProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const handleOpenChange = useCallback(
    (open: boolean) => {
      if (isSaving) return;
      setIsOpen(open);
      if (open) {
        const currentIndex = value ? options.indexOf(value) : -1;
        setFocusedIndex(currentIndex);
      } else {
        setFocusedIndex(-1);
      }
    },
    [isSaving, options, value]
  );

  const handleSelect = useCallback(
    async (newValue: T) => {
      if (newValue === value) {
        setIsOpen(false);
        return;
      }

      setIsOpen(false);
      setIsSaving(true);
      try {
        await onSave(newValue);
      } catch (err) {
        console.error('Failed to save:', err);
      } finally {
        setIsSaving(false);
      }
    },
    [value, onSave]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (isSaving || !isOpen) return;

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex(prev => (prev + 1) % options.length);
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex(prev => (prev - 1 + options.length) % options.length);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedIndex >= 0) {
            handleSelect(options[focusedIndex]);
          }
          break;
      }
    },
    [isSaving, isOpen, focusedIndex, options, handleSelect]
  );

  const variant = value
    ? getVariant
      ? getVariant(value)
      : (value as PillProps['variant'])
    : 'default';

  return (
    <Popover open={isOpen} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button className={cn(triggerStyles(), className)}>
          <Pill variant={variant}>
            <span className="relative inline-flex items-center justify-center">
              <span className={cn(isSaving && 'invisible')}>{value ?? placeholder}</span>
              {isSaving && <Spinner size="sm" className="absolute h-3 w-3" />}
            </span>
          </Pill>
        </button>
      </PopoverTrigger>
      <PopoverContent className="p-space-0 overflow-hidden" onKeyDown={handleKeyDown}>
        <div
          role="listbox"
          className="gap-space-xs p-space-sm flex flex-col items-center"
        >
          {options.map((option, index) => {
            const optionVariant = getVariant
              ? getVariant(option)
              : (option as PillProps['variant']);
            const isFocused = index === focusedIndex;
            return (
              <div
                key={option}
                tabIndex={-1}
                className={cn(optionRowStyles())}
                onClick={() => handleSelect(option)}
                role="option"
                aria-selected={option === value}
              >
                <Pill
                  variant={optionVariant}
                  className={cn(
                    optionStyles(),
                    isFocused && 'brightness-90 dark:brightness-110'
                  )}
                >
                  {option}
                </Pill>
              </div>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
