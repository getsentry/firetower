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
  editable?: boolean;
  className?: string;
  getVariant?: (value: T) => PillProps['variant'];
}

export function EditablePill<T extends string>({
  value,
  options,
  onSave,
  editable = true,
  className,
  getVariant,
}: EditablePillProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const open = useCallback(() => {
    if (!editable || isSaving) return;
    setIsOpen(true);
  }, [editable, isSaving]);

  const close = useCallback(() => {
    setIsOpen(false);
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

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, close]);

  const variant = getVariant ? getVariant(value) : (value as PillProps['variant']);

  return (
    <>
      <div ref={triggerRef} className="relative inline-block">
        <Pill
          variant={variant}
          className={cn(editable && triggerStyles(), className)}
          onClick={editable ? open : undefined}
          role={editable ? 'button' : undefined}
          aria-haspopup={editable ? 'listbox' : undefined}
          aria-expanded={editable ? isOpen : undefined}
        >
          {isSaving ? <Spinner size="sm" /> : value}
        </Pill>

        {isOpen && (
          <div ref={popoverRef} className={cn(popoverStyles())} role="listbox">
            {options.map(option => {
              const optionVariant = getVariant
                ? getVariant(option)
                : (option as PillProps['variant']);
              return (
                <div
                  key={option}
                  className={cn(optionRowStyles())}
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
