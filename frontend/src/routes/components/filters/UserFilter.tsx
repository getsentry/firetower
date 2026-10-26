import {useEffect, useMemo, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useInfiniteQuery, useQuery} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Tag} from 'components/Tag';
import {Pencil, XIcon} from 'lucide-react';

import {
  background,
  border,
  content,
  fontSize,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import {currentUserQueryOptions} from '../../queries/currentUserQueryOptions';
import {usersInfiniteQueryOptions} from '../../queries/usersQueryOptions';
import {EMPTY_FILTER_SENTINEL} from '../../types';
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
          aria-label={`Remove ${v === EMPTY_FILTER_SENTINEL ? 'Empty' : v}`}
        >
          <XIcon {...stylex.props(styles.removeIcon)} />
        </Button>
      }
    >
      {v === EMPTY_FILTER_SENTINEL ? (
        <span {...stylex.props(styles.emptyValue)}>Empty</span>
      ) : (
        v
      )}
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
    <div {...stylex.props(styles.tags)}>
      {selected.map(v => (
        <Tag
          key={v}
          style={styles.tag}
          onClick={open}
          action={
            <Button
              variant="close"
              size={null}
              onClick={e => {
                e.stopPropagation();
                remove(v);
              }}
              aria-label={`Remove ${v === EMPTY_FILTER_SENTINEL ? 'Empty' : v}`}
            >
              <XIcon {...stylex.props(styles.removeIcon)} />
            </Button>
          }
        >
          {v === EMPTY_FILTER_SENTINEL ? (
            <span {...stylex.props(styles.emptyValue)}>Empty</span>
          ) : (
            v
          )}
        </Tag>
      ))}
    </div>
  );
}

function EmptyPlaceholder({open}: {open: () => void}) {
  return (
    <button
      type="button"
      tabIndex={-1}
      {...stylex.props(styles.placeholder)}
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

  const {data: currentUser} = useQuery(currentUserQueryOptions());

  const {
    data: users = [],
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    ...usersInfiniteQueryOptions(debouncedSearch),
    enabled: isEditing,
  });

  const showEmptyOption =
    !selected.includes(EMPTY_FILTER_SENTINEL) &&
    (!inputValue || 'empty'.includes(inputValue.toLowerCase()));

  const available = useMemo(() => {
    const notSelected = users.filter(u => !selected.includes(u.email));

    if (!currentUser || selected.includes(currentUser.email)) {
      return notSelected;
    }

    const matchesSearch =
      !debouncedSearch ||
      currentUser.name.toLowerCase().includes(debouncedSearch.toLowerCase()) ||
      currentUser.email.toLowerCase().includes(debouncedSearch.toLowerCase());

    if (!matchesSearch) return notSelected;

    const rest = notSelected.filter(u => u.email !== currentUser.email);
    return [currentUser, ...rest];
  }, [users, selected, currentUser, debouncedSearch]);

  const allOptions = useMemo(() => {
    const emails = available.map(u => u.email);
    return showEmptyOption ? [EMPTY_FILTER_SENTINEL, ...emails] : emails;
  }, [available, showEmptyOption]);

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
      <div {...stylex.props(styles.heading)}>
        <h3 {...stylex.props(styles.label)}>{label}</h3>
        <Button
          variant="icon"
          onClick={open}
          aria-label={`Edit ${label}`}
          style={[styles.editButton, isEditing && styles.hidden]}
        >
          <Pencil {...stylex.props(styles.editIcon)} />
        </Button>
      </div>

      <div {...stylex.props(styles.editor, isEditing && styles.editing)}>
        {isEditing ? (
          <div {...stylex.props(styles.editingTags)}>
            <EditingTags selected={selected} toggle={toggle} />
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown(allOptions)}
              placeholder="Search users..."
              {...stylex.props(styles.input)}
            />
          </div>
        ) : (
          <SelectedValues selected={selected} open={open} remove={remove} />
        )}

        {isEditing ? (
          <div {...stylex.props(styles.dropdown)}>
            <div {...stylex.props(styles.options)}>
              {showEmptyOption ? (
                <button
                  type="button"
                  onClick={() => {
                    toggle(EMPTY_FILTER_SENTINEL);
                    setInputValue('');
                    setFocusedIndex(0);
                    inputRef.current?.focus();
                  }}
                  {...stylex.props(
                    styles.option,
                    focusedIndex === 0 ? styles.focusedOption : styles.idleOption
                  )}
                >
                  <span {...stylex.props(styles.emptyValue)}>Empty</span>
                </button>
              ) : null}
              {available.length > 0 ? (
                available.map((user, index) => {
                  const adjustedIndex = showEmptyOption ? index + 1 : index;
                  return (
                    <button
                      key={user.email}
                      type="button"
                      onClick={() => {
                        toggle(user.email);
                        setInputValue('');
                        setFocusedIndex(0);
                        inputRef.current?.focus();
                      }}
                      {...stylex.props(
                        styles.option,
                        adjustedIndex === focusedIndex
                          ? styles.focusedOption
                          : styles.idleOption
                      )}
                    >
                      <span>{user.name}</span>{' '}
                      <span {...stylex.props(styles.email)}>{user.email}</span>
                    </button>
                  );
                })
              ) : !showEmptyOption ? (
                <p {...stylex.props(styles.emptyResults)}>No users found</p>
              ) : null}
              <div ref={scrollSentinelRef} />
            </div>
          </div>
        ) : null}
      </div>

      {isEditing ? (
        <div {...stylex.props(styles.backdrop)} aria-hidden="true" onClick={close} />
      ) : null}
    </div>
  );
}

const styles = stylex.create({
  removeIcon: {height: 14, width: 14},
  emptyValue: {color: content.disabled, fontStyle: 'italic'},
  tags: {gap: space.sm, display: 'flex', flexWrap: 'wrap', userSelect: 'none'},
  tag: {
    backgroundColor: {
      default: background.tertiary,
      ':hover': background.transparentNeutralMuted,
      '@media (prefers-color-scheme: dark)': {
        default: background.secondary,
        ':hover': background.transparentNeutralMuted,
      },
    },
    cursor: 'pointer',
  },
  placeholder: {
    fontSize: fontSize.sm,
    color: content.disabled,
    cursor: 'pointer',
    fontStyle: 'italic',
    userSelect: 'none',
  },
  heading: {
    marginBottom: space.md,
    gap: space.xs,
    display: 'flex',
    alignItems: 'center',
  },
  label: {fontSize: fontSize.md, color: content.secondary, fontWeight: 600},
  editIcon: {height: 16, width: 16},
  editingTags: {
    gap: space.sm,
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    userSelect: 'none',
  },
  input: {
    paddingInline: space.sm,
    paddingBlock: space.xs,
    fontSize: fontSize.sm,
    color: {default: null, '::placeholder': content.disabled},
    minWidth: '100px',
    flex: '1 1 0%',
    backgroundColor: 'transparent',
  },
  dropdown: {
    marginTop: space.xs,
    borderRadius: radius.md,
    backgroundColor: background.primary,
    position: 'absolute',
    right: 0,
    left: 0,
    zIndex: 50,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: border.secondary,
    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  },
  options: {
    padding: space.sm,
    maxHeight: '200px',
    scrollbarWidth: 'none',
    overflowY: 'auto',
  },
  email: {color: content.disabled},
  emptyResults: {
    color: content.disabled,
    paddingInline: space.md,
    paddingBlock: space.sm,
    fontSize: fontSize.sm,
  },
  backdrop: {position: 'fixed', inset: 0, zIndex: 40, backgroundColor: 'transparent'},
  editButton: {transitionProperty: 'none'},
  hidden: {visibility: 'hidden'},
  editor: {position: 'relative'},
  editing: {zIndex: 50},
  option: {
    width: '100%',
    textAlign: 'left',
    paddingInline: space.md,
    paddingBlock: space.sm,
    cursor: 'pointer',
    borderRadius: radius.sm,
    fontSize: fontSize.sm,
  },
  focusedOption: {backgroundColor: background.secondary},
  idleOption: {
    backgroundColor: {default: null, ':hover': background.transparentNeutralMuted},
  },
});
