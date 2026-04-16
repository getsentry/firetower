import {useEffect, useRef, useState} from 'react';
import {useInfiniteQuery} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Tag} from 'components/Tag';
import {Pencil, XIcon} from 'lucide-react';
import {cn} from 'utils/cn';

import {usersInfiniteQueryOptions} from '../../queries/usersQueryOptions';
import {type ArrayFilterKey} from '../useActiveFilters';

import {useFilterEditor} from './useFilterEditor';

interface UserFilterProps {
  label: string;
  filterKey: ArrayFilterKey;
}

function EditingTags({
  selected,
  toggle,
}: {
  selected: string[];
  toggle: (value: string) => void;
}) {
  return selected.map(v => (
    <Tag
      key={v}
      action={
        <Button
          variant="close"
          size={null}
          onClick={() => toggle(v)}
          aria-label={`Remove ${v}`}
        >
          <XIcon className="h-3.5 w-3.5" />
        </Button>
      }
    >
      {v}
    </Tag>
  ));
}

function ReadOnlyTags({
  selected,
  open,
  remove,
}: {
  selected: string[];
  open: () => void;
  remove: (value: string) => void;
}) {
  return (
    <div className="gap-space-sm flex flex-wrap select-none">
      {selected.map(v => (
        <Tag
          key={v}
          className="cursor-pointer"
          onClick={open}
          action={
            <Button
              variant="close"
              size={null}
              onClick={e => {
                e.stopPropagation();
                remove(v);
              }}
              aria-label={`Remove ${v}`}
            >
              <XIcon className="h-3.5 w-3.5" />
            </Button>
          }
        >
          {v}
        </Tag>
      ))}
    </div>
  );
}

function EmptyPlaceholder({open}: {open: () => void}) {
  return (
    <button
      type="button"
      className="text-size-sm text-content-disabled cursor-pointer italic select-none"
      onClick={open}
    >
      Any
    </button>
  );
}

function SelectedValues({
  selected,
  open,
  remove,
}: {
  selected: string[];
  open: () => void;
  remove: (value: string) => void;
}) {
  if (selected.length > 0) {
    return <ReadOnlyTags selected={selected} open={open} remove={remove} />;
  }

  return <EmptyPlaceholder open={open} />;
}

export function UserFilter({label, filterKey}: UserFilterProps) {
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const scrollSentinelRef = useRef<HTMLDivElement>(null);

  const {
    isEditing,
    selected,
    inputValue,
    focusedIndex,
    inputRef,
    setInputValue,
    setFocusedIndex,
    toggle,
    remove,
    open,
    close,
    handleKeyDown,
  } = useFilterEditor({
    filterKey,
    onClose: () => setDebouncedSearch(''),
    onOpen: () => setDebouncedSearch(''),
  });

  const {
    data: users = [],
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    ...usersInfiniteQueryOptions(debouncedSearch),
    enabled: isEditing,
  });

  const available = users.filter(u => !selected.includes(u.email));

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(inputValue), 300);
    return () => clearTimeout(timer);
  }, [inputValue]);

  useEffect(() => {
    const target = scrollSentinelRef.current;
    if (!target || !isEditing) return;

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      {threshold: 0.1}
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [isEditing, fetchNextPage, hasNextPage, isFetchingNextPage]);

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          className={cn('transition-none', isEditing && 'invisible')}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center select-none">
            <EditingTags selected={selected} toggle={toggle} />
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown(available.map(u => u.email))}
              placeholder="Search users..."
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : (
          <SelectedValues selected={selected} open={open} remove={remove} />
        )}

        {isEditing ? (
          <div className="mt-space-xs rounded-radius-md bg-background-primary absolute right-0 left-0 z-50 border border-gray-200 shadow-lg">
            <div className="p-space-sm max-h-[200px] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {available.length > 0 ? (
                available.map((user, index) => (
                  <button
                    key={user.email}
                    type="button"
                    onClick={() => {
                      toggle(user.email);
                      setInputValue('');
                      setFocusedIndex(0);
                      inputRef.current?.focus();
                    }}
                    className={cn(
                      'w-full text-left px-space-md py-space-sm cursor-pointer rounded-radius-sm text-size-sm',
                      index === focusedIndex
                        ? 'bg-background-secondary'
                        : 'hover:bg-background-transparent-neutral-muted'
                    )}
                  >
                    <span>{user.name}</span>{' '}
                    <span className="text-content-disabled">{user.email}</span>
                  </button>
                ))
              ) : (
                <p className="text-content-disabled px-space-md py-space-sm text-size-sm">
                  No users found
                </p>
              )}
              <div ref={scrollSentinelRef} />
            </div>
          </div>
        ) : null}
      </div>

      {isEditing ? (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={close}
        />
      ) : null}
    </div>
  );
}
