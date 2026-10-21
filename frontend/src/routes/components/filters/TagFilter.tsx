import * as stylex from '@stylexjs/stylex';
import {useQuery} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Tag} from 'components/Tag';
import {Pencil, XIcon} from 'lucide-react';

import {
  background,
  content,
  fontSize,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import {tagsQueryOptions, type TagType} from '../../$incidentId/queries/tagsQueryOptions';
import {EMPTY_FILTER_SENTINEL} from '../../types';
import {type ArrayFilterKey} from '../useActiveFilters';

import {useFilterEditor} from './useFilterEditor';

interface TagFilterProps {
  label: string;
  filterKey: ArrayFilterKey;
  tagType: TagType;
}

export function TagFilter({label, filterKey, tagType}: TagFilterProps) {
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
  } = useFilterEditor({filterKey});
  const {data: suggestions = []} = useQuery(tagsQueryOptions(tagType));

  const available: string[] = [
    ...(!selected.includes(EMPTY_FILTER_SENTINEL) &&
    'empty'.includes(inputValue.toLowerCase())
      ? [EMPTY_FILTER_SENTINEL]
      : []),
    ...suggestions.filter(
      (s: string) =>
        s !== EMPTY_FILTER_SENTINEL &&
        !selected.includes(s) &&
        s.toLowerCase().includes(inputValue.toLowerCase())
    ),
  ];

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
            {selected.map(v => (
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
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(0);
              }}
              onKeyDown={handleKeyDown(available)}
              placeholder="Add..."
              {...stylex.props(styles.input)}
            />
          </div>
        ) : selected.length > 0 ? (
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
        ) : (
          <button
            type="button"
            tabIndex={-1}
            {...stylex.props(styles.placeholder)}
            onClick={open}
          >
            Any
          </button>
        )}

        {isEditing && available.length > 0 ? (
          <div {...stylex.props(styles.dropdown)}>
            <div {...stylex.props(styles.options)}>
              {available.map((option: string, index: number) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    toggle(option);
                    setInputValue('');
                    setFocusedIndex(0);
                    inputRef.current?.focus();
                  }}
                  {...stylex.props(
                    styles.option,
                    index === focusedIndex ? styles.focusedOption : styles.idleOption
                  )}
                >
                  {option === EMPTY_FILTER_SENTINEL ? (
                    <span {...stylex.props(styles.emptyValue)}>Empty</span>
                  ) : (
                    option
                  )}
                </button>
              ))}
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
  removeIcon: {height: 14, width: 14},
  emptyValue: {color: content.disabled, fontStyle: 'italic'},
  input: {
    paddingInline: space.sm,
    paddingBlock: space.xs,
    fontSize: fontSize.sm,
    color: {default: null, '::placeholder': content.disabled},
    minWidth: '100px',
    flex: '1 1 0%',
    backgroundColor: 'transparent',
  },
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
    borderColor: '#e5e7eb',
    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  },
  options: {
    padding: space.sm,
    maxHeight: '200px',
    scrollbarWidth: 'none',
    overflowY: 'auto',
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
