import {useEffect, useId, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Check, ChevronDown} from 'lucide-react';

import type {StyledProps} from '../styles/props';
import {background, content, fontSize, radius, space} from '../styles/tokens.stylex';

import {buttonStyles} from './buttonStyles';
import {Input} from './Input';
import {Popover, PopoverContent, PopoverTrigger} from './Popover';

export interface SelectOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

interface SearchableSelectProps<T extends string> extends StyledProps<object> {
  label: string;
  value: T;
  options: readonly SelectOption<T>[];
  onChange: (value: T) => void;
  placeholder?: string;
}

export function SearchableSelect<T extends string>({
  label,
  value,
  options,
  onChange,
  style,
  placeholder = 'Select…',
}: SearchableSelectProps<T>) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const focusedRef = useRef<HTMLButtonElement>(null);
  const listId = useId();
  const selected = options.find(option => option.value === value);
  const needle = query.trim().toLocaleLowerCase();
  const available = options.filter(option =>
    `${option.label} ${option.description ?? ''}`.toLocaleLowerCase().includes(needle)
  );
  const activeId = available[focusedIndex] ? `${listId}-${focusedIndex}` : undefined;

  const openChange = (open: boolean) => {
    setIsOpen(open);
    setQuery('');
    setFocusedIndex(
      Math.max(
        0,
        options.findIndex(option => option.value === value)
      )
    );
  };
  const choose = (option: SelectOption<T>) => {
    openChange(false);
    if (option.value !== value) onChange(option.value);
  };

  useEffect(() => {
    focusedRef.current?.scrollIntoView({block: 'nearest'});
  }, [focusedIndex, query]);

  return (
    <Popover open={isOpen} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          role="combobox"
          aria-label={label}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-controls={isOpen ? listId : undefined}
          onKeyDown={event => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault();
              openChange(true);
            }
          }}
          {...stylex.props(
            buttonStyles({variant: 'secondary', size: 'sm'}),
            styles.trigger,
            style
          )}
        >
          <span {...stylex.props(styles.value)}>{selected?.label ?? placeholder}</span>
          <ChevronDown size={14} aria-hidden="true" {...stylex.props(styles.chevron)} />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        collisionPadding={16}
        style={styles.popover}
        onOpenAutoFocus={event => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <Input
          ref={inputRef}
          aria-label={`Search ${label}`}
          aria-controls={listId}
          aria-activedescendant={activeId}
          value={query}
          placeholder="Search…"
          onChange={event => {
            setQuery(event.target.value);
            setFocusedIndex(0);
          }}
          onKeyDown={event => {
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
              event.preventDefault();
              if (available.length) {
                const step = event.key === 'ArrowDown' ? 1 : -1;
                setFocusedIndex(
                  index => (index + step + available.length) % available.length
                );
              }
            } else if (event.key === 'Enter') {
              event.preventDefault();
              const option = available[focusedIndex];
              if (option) choose(option);
            }
          }}
        />
        <div
          id={listId}
          role="listbox"
          aria-label={label}
          {...stylex.props(styles.options)}
        >
          {available.map((option, index) => (
            <button
              key={option.value}
              ref={index === focusedIndex ? focusedRef : undefined}
              id={`${listId}-${index}`}
              type="button"
              role="option"
              tabIndex={-1}
              aria-selected={option.value === value}
              onMouseDown={event => event.preventDefault()}
              onClick={() => choose(option)}
              {...stylex.props(
                styles.option,
                index === focusedIndex ? styles.focused : null
              )}
            >
              <span>
                <span>{option.label}</span>
                {option.description ? (
                  <span {...stylex.props(styles.description)}>{option.description}</span>
                ) : null}
              </span>
              {option.value === value ? <Check size={14} aria-hidden="true" /> : null}
            </button>
          ))}
          {available.length === 0 ? (
            <p role="status" {...stylex.props(styles.empty)}>
              No matches found
            </p>
          ) : null}
        </div>
      </PopoverContent>
    </Popover>
  );
}

const styles = stylex.create({
  trigger: {minWidth: 0, maxWidth: '100%', textAlign: 'left'},
  value: {
    minWidth: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  chevron: {flexShrink: 0},
  popover: {width: 320, maxWidth: 'calc(100vw - 32px)'},
  options: {marginTop: space.sm, maxHeight: 248, overflowY: 'auto'},
  option: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: space.md,
    width: '100%',
    textAlign: 'left',
    padding: space.md,
    borderRadius: radius.sm,
    color: content.primary,
    fontSize: fontSize.md,
    cursor: 'pointer',
    backgroundColor: {default: 'transparent', ':hover': background.secondary},
  },
  focused: {backgroundColor: background.transparentAccentMuted},
  description: {display: 'block', color: content.secondary, fontSize: fontSize.sm},
  empty: {padding: space.lg, color: content.secondary, fontSize: fontSize.sm},
});
