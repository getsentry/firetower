import {useCallback, useEffect, useRef, useState} from 'react';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Pill, type PillProps} from './Pill';
import {Spinner} from './Spinner';

const popoverStyles = cva([
  'absolute',
  'z-50',
  'mt-space-xs',
  'rounded-radius-md',
  'border',
  'border-gray-200',
  'bg-background-primary',
  'shadow-lg',
  'p-space-sm',
  'flex',
  'flex-col',
  'gap-space-xs',
  'min-w-max',
]);

const optionRowStyles = cva([
  'w-full',
  'cursor-pointer',
  'flex',
  'items-center',
  'rounded-radius-md',
  'transition-all',
  'hover:bg-gray-100',
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
]);

const overlayStyles = cva(['fixed', 'inset-0', 'z-40', 'bg-transparent']);

export interface EditablePillProps<T extends string> {
  value: T;
  options: readonly T[];
  onSave: (newValue: T) => Promise<void>;
  className?: string;
  getVariant?: (value: T) => PillProps['variant'];
}

export function EditablePill<T extends string>({
  value,
  options,
  onSave,
  className,
  getVariant,
}: EditablePillProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const open = useCallback(() => {
    if (isSaving) return;
    setIsOpen(true);
    const currentIndex = options.indexOf(value);
    setFocusedIndex(currentIndex);
  }, [isSaving, options, value]);

  const close = useCallback(() => {
    setIsOpen(false);
    setFocusedIndex(-1);
    triggerRef.current?.focus();
  }, []);

  const handleSelect = useCallback(
    async (newValue: T) => {
      if (newValue === value) {
        close();
        return;
      }

      close();
      setIsSaving(true);
      try {
        await onSave(newValue);
      } catch (err) {
        console.error('Failed to save:', err);
      } finally {
        setIsSaving(false);
      }
    },
    [value, onSave, close]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (isSaving) return;

      if (!isOpen) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open();
        }
        return;
      }

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
        case 'Escape':
          event.preventDefault();
          close();
          break;
      }
    },
    [isSaving, isOpen, open, close, focusedIndex, options, handleSelect]
  );

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        close();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, close]);

  const variant = getVariant ? getVariant(value) : (value as PillProps['variant']);

  return (
    <>
      <div className="relative inline-block">
        <button
          ref={triggerRef}
          onClick={open}
          onKeyDown={handleKeyDown}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          className={cn(triggerStyles(), className)}
        >
          <Pill variant={variant}>
            <span className="relative inline-flex items-center justify-center">
              <span className={cn(isSaving && 'invisible')}>{value}</span>
              {isSaving && (
                <Spinner size="sm" className="absolute h-3 w-3" />
              )}
            </span>
          </Pill>
        </button>

        {isOpen && (
          <div ref={popoverRef} className={cn(popoverStyles())} role="listbox">
            {options.map((option, index) => {
              const optionVariant = getVariant
                ? getVariant(option)
                : (option as PillProps['variant']);
              const isFocused = index === focusedIndex;
              return (
                <div
                  key={option}
                  className={cn(
                    optionRowStyles(),
                    isFocused && 'bg-gray-100'
                  )}
                  onClick={() => handleSelect(option)}
                  role="option"
                  aria-selected={option === value}
                >
                  <Pill variant={optionVariant} className={cn(optionStyles())}>
                    {option}
                  </Pill>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {isOpen && <div className={cn(overlayStyles())} aria-hidden="true" />}
    </>
  );
}
