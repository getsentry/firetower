import {useCallback, useState} from 'react';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, radius, space} from '../styles/tokens.stylex';

import {Pill, type PillProps} from './Pill';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';
import {Spinner} from './Spinner';

export interface EditablePillProps<T extends string> extends StyledProps<object> {
  value: T | null;
  options: readonly T[];
  onSave: (newValue: T) => Promise<void>;
  getVariant?: (value: T) => PillProps['variant'];
  placeholder?: string;
}

export function EditablePill<T extends string>({
  value,
  options,
  onSave,
  style,
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
        <button {...stylex.props(styles.trigger, style)}>
          <Pill variant={variant}>
            <span {...stylex.props(styles.content)}>
              <span {...stylex.props(isSaving && styles.invisible)}>
                {value ?? placeholder}
              </span>
              {isSaving && <Spinner size="sm" style={styles.spinner} />}
            </span>
          </Pill>
        </button>
      </PopoverTrigger>
      <PopoverContent style={styles.popover} onKeyDown={handleKeyDown}>
        <div role="listbox" {...stylex.props(styles.options)}>
          {options.map((option, index) => {
            const optionVariant = getVariant
              ? getVariant(option)
              : (option as PillProps['variant']);
            const isFocused = index === focusedIndex;
            return (
              <div
                key={option}
                tabIndex={-1}
                {...stylex.props(styles.optionRow, isFocused && styles.focused)}
                onClick={() => handleSelect(option)}
                role="option"
                aria-selected={option === value}
              >
                <Pill variant={optionVariant} style={styles.option}>
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

const styles = stylex.create({
  optionRow: {
    width: '100%',
    justifyContent: 'center',
    display: 'flex',
    alignItems: 'center',
    cursor: 'pointer',
    borderRadius: radius.md,
    paddingInline: space.xs,
    paddingBlock: space['2xs'],
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
    backgroundColor: {default: null, ':hover': background.tertiary},
  },
  option: {pointerEvents: 'none'},
  trigger: {
    position: 'relative',
    display: 'inline-flex',
    cursor: 'pointer',
    alignItems: 'center',
    borderRadius: radius.full,
    lineHeight: 1,
    userSelect: 'none',
    transitionProperty: 'all',
    transitionDuration: '150ms',
    transform: {default: null, ':hover': 'scale(1.05)', ':active': 'scale(0.95)'},
    boxShadow: {
      default: null,
      ':hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    },
  },
  content: {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  spinner: {position: 'absolute', height: 12, width: 12},
  popover: {padding: space['0'], overflow: 'hidden'},
  options: {padding: space.xs, display: 'flex', flexDirection: 'column'},
  invisible: {visibility: 'hidden'},
  focused: {backgroundColor: background.tertiary},
});
