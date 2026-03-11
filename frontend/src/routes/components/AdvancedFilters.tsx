import {useCallback, useEffect, useRef, useState} from 'react';
import {useInfiniteQuery, useQuery} from '@tanstack/react-query';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Calendar} from 'components/Calendar';
import {Card} from 'components/Card';
import {Pill, type PillProps} from 'components/Pill';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {Tag} from 'components/Tag';
import {Pencil, SlidersHorizontalIcon, XIcon} from 'lucide-react';
import {cn} from 'utils/cn';

import {tagsQueryOptions, type TagType} from '../$incidentId/queries/tagsQueryOptions';
import {usersInfiniteQueryOptions} from '../queries/usersQueryOptions';
import {ServiceTierSchema, SeveritySchema} from '../types';

import {useActiveFilters, type ArrayFilterKey} from './useActiveFilters';

export function FilterTrigger({open, onToggle}: {open: boolean; onToggle: () => void}) {
  const navigate = useNavigate();
  const {activeCount} = useActiveFilters();

  return (
    <div className="flex items-center gap-space-md">
      {activeCount > 0 && (
        <button
          type="button"
          className="text-content-accent text-size-sm cursor-pointer hover:underline"
          onClick={() => {
            navigate({
              to: '/',
              search: prev => ({
                ...prev,
                severity: undefined,
                service_tier: undefined,
                affected_service: undefined,
                root_cause: undefined,
                impact_type: undefined,
                affected_region: undefined,
                captain: undefined,
                reporter: undefined,
                created_after: undefined,
                created_before: undefined,
              }),
              replace: true,
            });
          }}
          data-testid="clear-all-filters"
        >
          Clear all filters
        </button>
      )}
      <Button
        variant="secondary"
        size="sm"
        onClick={onToggle}
        aria-expanded={open}
        data-testid="advanced-filters-toggle"
      >
        <SlidersHorizontalIcon className="h-3.5 w-3.5" />
        {open ? 'Hide filters' : 'Show filters'}
        {activeCount > 0 && (
          <span className="bg-background-accent-vibrant text-content-on-vibrant-light ml-space-2xs inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-xs leading-none">
            {activeCount}
          </span>
        )}
      </Button>
    </div>
  );
}

type PillVariant = NonNullable<PillProps['variant']>;

interface PillFilterProps<T extends PillVariant> {
  label: string;
  filterKey: ArrayFilterKey;
  options: readonly T[];
}

function PillFilter<T extends PillVariant>({
  label,
  filterKey,
  options,
}: PillFilterProps<T>) {
  const navigate = useNavigate();
  const {search} = useActiveFilters();
  const committed = ((search[filterKey] as string[] | undefined) ?? []) as string[];
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = isEditing ? draft : committed;

  const available = options.filter(
    o => !selected.includes(o) && o.toLowerCase().includes(inputValue.toLowerCase())
  );

  const toggle = useCallback((value: string) => {
    setDraft(prev =>
      prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]
    );
  }, []);

  const close = useCallback(() => {
    setIsEditing(false);
    setInputValue('');
    setFocusedIndex(0);
    setDraft(prev => {
      navigate({
        to: '/',
        search: s => ({...s, [filterKey]: prev.length > 0 ? prev : undefined}),
        replace: true,
      });
      return prev;
    });
  }, [navigate, filterKey]);

  const open = () => {
    setDraft(committed);
    setIsEditing(true);
    setInputValue('');
    setFocusedIndex(0);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isEditing, close]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev + 1) % available.length);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev - 1 + available.length) % available.length);
        }
        break;
      case 'Enter':
      case ' ':
        if (focusedIndex >= 0 && focusedIndex < available.length) {
          e.preventDefault();
          toggle(available[focusedIndex]);
          setInputValue('');
          setFocusedIndex(0);
          inputRef.current?.focus();
        } else if (e.key === 'Enter' && !inputValue.trim()) {
          close();
        }
        break;
      case 'Backspace':
        if (inputValue === '' && selected.length > 0) {
          toggle(selected[selected.length - 1]);
        }
        break;
    }
  };

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          className={cn(isEditing && 'invisible')}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center">
            {selected.map(v => (
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
                <Pill variant={v as T}>{v}</Pill>
              </Tag>
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Add..."
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : selected.length > 0 ? (
          <div className="gap-space-sm flex flex-wrap">
            {selected.map(v => (
              <Tag key={v}>
                <Pill variant={v as T}>{v}</Pill>
              </Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">Any</p>
        )}

        {isEditing && available.length > 0 && (
          <div className="mt-space-xs rounded-radius-md bg-background-primary absolute right-0 left-0 z-50 border border-gray-200 shadow-lg">
            <div className="p-space-sm max-h-[200px] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {available.map((option, index) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    toggle(option);
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
                  <Pill variant={option}>{option}</Pill>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {isEditing && (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={close}
        />
      )}
    </div>
  );
}

interface TagFilterProps {
  label: string;
  filterKey: ArrayFilterKey;
  tagType: TagType;
}

function TagFilter({label, filterKey, tagType}: TagFilterProps) {
  const navigate = useNavigate();
  const {search} = useActiveFilters();
  const committed = ((search[filterKey] as string[] | undefined) ?? []) as string[];
  const {data: suggestions = []} = useQuery(tagsQueryOptions(tagType));
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = isEditing ? draft : committed;

  const available = suggestions.filter(
    s => !selected.includes(s) && s.toLowerCase().includes(inputValue.toLowerCase())
  );

  const toggle = useCallback((value: string) => {
    setDraft(prev =>
      prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]
    );
  }, []);

  const close = useCallback(() => {
    setIsEditing(false);
    setInputValue('');
    setFocusedIndex(0);
    setDraft(prev => {
      navigate({
        to: '/',
        search: s => ({...s, [filterKey]: prev.length > 0 ? prev : undefined}),
        replace: true,
      });
      return prev;
    });
  }, [navigate, filterKey]);

  const open = () => {
    setDraft(committed);
    setIsEditing(true);
    setInputValue('');
    setFocusedIndex(0);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isEditing, close]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev + 1) % available.length);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev - 1 + available.length) % available.length);
        }
        break;
      case 'Enter':
      case ' ':
        if (focusedIndex >= 0 && focusedIndex < available.length) {
          e.preventDefault();
          toggle(available[focusedIndex]);
          setInputValue('');
          setFocusedIndex(0);
          inputRef.current?.focus();
        } else if (e.key === 'Enter' && !inputValue.trim()) {
          close();
        }
        break;
      case 'Backspace':
        if (inputValue === '' && selected.length > 0) {
          toggle(selected[selected.length - 1]);
        }
        break;
    }
  };

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          className={cn(isEditing && 'invisible')}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center">
            {selected.map(v => (
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
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Add..."
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : selected.length > 0 ? (
          <div className="gap-space-sm flex flex-wrap">
            {selected.map(v => (
              <Tag key={v}>{v}</Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">Any</p>
        )}

        {isEditing && available.length > 0 && (
          <div className="mt-space-xs rounded-radius-md bg-background-primary absolute right-0 left-0 z-50 border border-gray-200 shadow-lg">
            <div className="p-space-sm max-h-[200px] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {available.map((option, index) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    toggle(option);
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
                  {option}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {isEditing && (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={close}
        />
      )}
    </div>
  );
}

interface UserFilterProps {
  label: string;
  filterKey: ArrayFilterKey;
}

function UserFilter({label, filterKey}: UserFilterProps) {
  const navigate = useNavigate();
  const {search} = useActiveFilters();
  const committed = ((search[filterKey] as string[] | undefined) ?? []) as string[];
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollSentinelRef = useRef<HTMLDivElement>(null);

  const selected = isEditing ? draft : committed;

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

  const toggle = useCallback((value: string) => {
    setDraft(prev =>
      prev.includes(value) ? prev.filter(v => v !== value) : [...prev, value]
    );
  }, []);

  const close = useCallback(() => {
    setIsEditing(false);
    setInputValue('');
    setDebouncedSearch('');
    setFocusedIndex(0);
    setDraft(prev => {
      navigate({
        to: '/',
        search: s => ({...s, [filterKey]: prev.length > 0 ? prev : undefined}),
        replace: true,
      });
      return prev;
    });
  }, [navigate, filterKey]);

  const open = () => {
    setDraft(committed);
    setIsEditing(true);
    setInputValue('');
    setDebouncedSearch('');
    setFocusedIndex(0);
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isEditing, close]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev + 1) % available.length);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        if (available.length > 0) {
          setFocusedIndex(prev => (prev - 1 + available.length) % available.length);
        }
        break;
      case 'Enter':
      case ' ':
        if (focusedIndex >= 0 && focusedIndex < available.length) {
          e.preventDefault();
          toggle(available[focusedIndex].email);
          setInputValue('');
          setFocusedIndex(0);
          inputRef.current?.focus();
        } else if (e.key === 'Enter' && !inputValue.trim()) {
          close();
        }
        break;
      case 'Backspace':
        if (inputValue === '' && selected.length > 0) {
          toggle(selected[selected.length - 1]);
        }
        break;
    }
  };

  return (
    <div>
      <div className="mb-space-md gap-space-xs flex items-center">
        <h3 className="text-size-md text-content-secondary font-semibold">{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          className={cn(isEditing && 'invisible')}
        >
          <Pencil className="h-4 w-4" />
        </Button>
      </div>

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center">
            {selected.map(v => (
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
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search users..."
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : selected.length > 0 ? (
          <div className="gap-space-sm flex flex-wrap">
            {selected.map(v => (
              <Tag key={v}>{v}</Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">Any</p>
        )}

        {isEditing && (
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
        )}
      </div>

      {isEditing && (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={close}
        />
      )}
    </div>
  );
}

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

function DateRangeFilter() {
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
        <div className="flex items-center gap-space-xs">
          <Popover
            open={editing === 'after'}
            onOpenChange={o => setEditing(o ? 'after' : null)}
          >
            <PopoverTrigger asChild>
              <Button variant="secondary" className="text-size-sm">
                {after ? formatDateDisplay(after) : 'Any'}
              </Button>
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
          {after && (
            <Button
              variant="close"
              onClick={() => update('created_after', undefined)}
              aria-label="Clear start date"
              size={null}
            >
              <XIcon className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
        <span className="text-content-disabled text-size-sm">to</span>
        <div className="flex items-center gap-space-xs">
          <Popover
            open={editing === 'before'}
            onOpenChange={o => setEditing(o ? 'before' : null)}
          >
            <PopoverTrigger asChild>
              <Button variant="secondary" className="text-size-sm">
                {before ? formatDateDisplay(before) : 'Any'}
              </Button>
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
          {before && (
            <Button
              variant="close"
              onClick={() => update('created_before', undefined)}
              aria-label="Clear end date"
              size={null}
            >
              <XIcon className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export function FilterPanel() {
  return (
    <Card className="flex flex-col gap-space-md" data-testid="advanced-filters">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-space-md">
        <PillFilter
          label="Severity"
          filterKey="severity"
          options={SeveritySchema.options}
        />
        <PillFilter
          label="Service Tier"
          filterKey="service_tier"
          options={ServiceTierSchema.options}
        />
        <TagFilter label="Impact Type" filterKey="impact_type" tagType="IMPACT_TYPE" />
        <TagFilter
          label="Affected Service"
          filterKey="affected_service"
          tagType="AFFECTED_SERVICE"
        />
        <TagFilter
          label="Affected Region"
          filterKey="affected_region"
          tagType="AFFECTED_REGION"
        />
        <TagFilter label="Root Cause" filterKey="root_cause" tagType="ROOT_CAUSE" />
        <UserFilter label="Captain" filterKey="captain" />
        <UserFilter label="Reporter" filterKey="reporter" />
        <DateRangeFilter />
      </div>
    </Card>
  );
}
