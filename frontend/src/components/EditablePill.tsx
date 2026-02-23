import type {ReactNode} from 'react';
import {useCallback, useState} from 'react';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Pill, type PillProps} from './Pill';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';
import {Spinner} from './Spinner';
import {Tooltip, TooltipContent, TooltipTrigger} from './Tooltip';

const optionRowStyles = cva([
  'w-full',
  'cursor-pointer',
  'flex',
  'items-center',
  'rounded-radius-md',
  'transition-all',
  'hover:bg-gray-100',
  'dark:hover:bg-neutral-800',
  'p-space-xs',
  '-m-space-xs',
]);

const optionStyles = cva(['pointer-events-none']);

const triggerStyles = cva([
  'cursor-pointer',
  'transition-all',
  'hover:shadow-md',
  'hover:scale-105',
  'active:scale-95',
  'relative',
  'rounded-full',
  'select-none',
]);

export interface EditablePillProps<T extends string> {
  value: T | null;
  options: readonly T[];
  onSave: (newValue: T) => Promise<void>;
  className?: string;
  getVariant?: (value: T) => PillProps['variant'];
  placeholder?: string;
  disabledOptions?: Partial<Record<T, ReactNode>>;
}

export function EditablePill<T extends string>({
  value,
  options,
  onSave,
  className,
  getVariant,
  placeholder = 'Not set',
  disabledOptions,
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
          if (
            focusedIndex >= 0 &&
            !(disabledOptions && options[focusedIndex] in disabledOptions)
          ) {
            handleSelect(options[focusedIndex]);
          }
          break;
      }
    },
    [isSaving, isOpen, focusedIndex, options, handleSelect, disabledOptions]
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
      <PopoverContent
        className="gap-space-xs p-space-sm flex flex-col"
        onKeyDown={handleKeyDown}
      >
        <div role="listbox">
          {options.map((option, index) => {
            const optionVariant = getVariant
              ? getVariant(option)
              : (option as PillProps['variant']);
            const isFocused = index === focusedIndex;
            const isDisabled = disabledOptions !== undefined && option in disabledOptions;
            const disabledMessage = disabledOptions?.[option];

            const row = (
              <div
                key={option}
                tabIndex={-1}
                className={cn(
                  optionRowStyles(),
                  isFocused && 'bg-gray-100 dark:bg-neutral-700',
                  isDisabled &&
                    'cursor-default opacity-50 hover:bg-transparent dark:hover:bg-transparent'
                )}
                onClick={isDisabled ? undefined : () => handleSelect(option)}
                role="option"
                aria-selected={option === value}
                aria-disabled={isDisabled}
              >
                <Pill variant={optionVariant} className={cn(optionStyles())}>
                  {option}
                </Pill>
              </div>
            );

            if (isDisabled) {
              return (
                <Tooltip key={option}>
                  <TooltipTrigger asChild>{row}</TooltipTrigger>
                  <TooltipContent side="bottom" className="max-w-xs">
                    {disabledMessage}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return row;
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
