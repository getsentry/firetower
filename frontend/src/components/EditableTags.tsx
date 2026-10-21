import {useCallback, useEffect, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Loader2, Pencil, Plus, X} from 'lucide-react';

import type {StyledProps} from '../styles/props';
import {
  background,
  border,
  content,
  fontSize,
  radius,
  space,
} from '../styles/tokens.stylex';

import {Button} from './Button';
import {GetHelpLink} from './GetHelpLink';
import {Tag} from './Tag';

export interface EditableTagsProps extends StyledProps<object> {
  tags: string[];
  onSave: (tags: string[]) => Promise<void>;
  label?: string;
  suggestions?: string[];
  placeholder?: string;
  emptyText?: string;
  allowTagCreation?: boolean;
  onCreateTag?: (name: string) => Promise<void>;
}

export function EditableTags({
  tags,
  onSave,
  label,
  suggestions = [],
  placeholder = 'Add...',
  emptyText = 'None specified',
  style,
  allowTagCreation = false,
  onCreateTag,
}: EditableTagsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftTags, setDraftTags] = useState<string[]>(tags);
  const [optimisticTags, setOptimisticTags] = useState<string[] | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [isCreating, setIsCreating] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const focusedOptionRef = useRef<HTMLButtonElement>(null);

  const resetState = () => {
    setInputValue('');
    setFocusedIndex(-1);
  };

  const open = () => {
    setDraftTags([...tags].sort((a, b) => a.localeCompare(b)));
    setOptimisticTags(null);
    setIsEditing(true);
    setSaveError(null);
    resetState();
  };

  const close = useCallback(() => {
    const tagsToSave = draftTags;
    setOptimisticTags(tagsToSave);
    setIsEditing(false);
    resetState();
    onSave(tagsToSave)
      .then(() => {
        setOptimisticTags(null);
        setSaveError(null);
      })
      .catch(err => {
        console.error('Failed to save:', err);
        setOptimisticTags(null);
        setSaveError('Failed to save. Please try again.');
      });
  }, [draftTags, onSave]);

  const sortedTags = [...tags].sort((a, b) => a.localeCompare(b));
  const tagsHaveCaughtUp =
    optimisticTags && JSON.stringify(sortedTags) === JSON.stringify(optimisticTags);
  const displayTags = optimisticTags && !tagsHaveCaughtUp ? optimisticTags : sortedTags;

  const filteredSuggestions = suggestions.filter(
    s => !draftTags.includes(s) && s.toLowerCase().includes(inputValue.toLowerCase())
  );

  const trimmedInput = inputValue.trim();
  const exactMatchExists = suggestions.some(
    s => s.toLowerCase() === trimmedInput.toLowerCase()
  );
  const alreadyInDraft = draftTags.some(
    t => t.toLowerCase() === trimmedInput.toLowerCase()
  );
  const showCreateOption =
    allowTagCreation &&
    onCreateTag &&
    trimmedInput &&
    !exactMatchExists &&
    !alreadyInDraft;

  const totalOptions = filteredSuggestions.length + (showCreateOption ? 1 : 0);

  const handleCreateTag = async () => {
    if (!onCreateTag || !trimmedInput || isCreating) return;

    setIsCreating(true);
    try {
      await onCreateTag(trimmedInput);
      setDraftTags(prev => [...prev, trimmedInput].sort((a, b) => a.localeCompare(b)));
      resetState();
      inputRef.current?.focus();
    } catch (err) {
      console.error('Failed to create tag:', err);
    } finally {
      setIsCreating(false);
    }
  };

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !draftTags.includes(trimmed)) {
      setDraftTags([...draftTags, trimmed].sort((a, b) => a.localeCompare(b)));
      resetState();
      inputRef.current?.focus();
    }
  };

  const removeTag = (tag: string) => {
    setDraftTags(draftTags.filter(t => t !== tag));
    inputRef.current?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (totalOptions > 0) {
          setFocusedIndex(prev => (prev + 1) % totalOptions);
        }
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (totalOptions > 0) {
          setFocusedIndex(prev => (prev - 1 + totalOptions) % totalOptions);
        }
        break;
      case 'Enter':
        event.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < totalOptions) {
          if (showCreateOption && focusedIndex === 0) {
            handleCreateTag();
          } else {
            const suggestionIndex = showCreateOption ? focusedIndex - 1 : focusedIndex;
            addTag(filteredSuggestions[suggestionIndex]);
          }
        } else if (!inputValue.trim()) {
          close();
        }
        break;
      case ' ':
        if (focusedIndex >= 0 && focusedIndex < totalOptions) {
          event.preventDefault();
          if (showCreateOption && focusedIndex === 0) {
            handleCreateTag();
          } else {
            const suggestionIndex = showCreateOption ? focusedIndex - 1 : focusedIndex;
            addTag(filteredSuggestions[suggestionIndex]);
          }
        }
        break;
      case 'Escape':
        event.preventDefault();
        close();
        break;
      case 'Backspace':
        if (inputValue === '' && draftTags.length > 0) {
          removeTag(draftTags[draftTags.length - 1]);
        }
        break;
    }
  };

  useEffect(() => {
    focusedOptionRef.current?.scrollIntoView({block: 'nearest'});
  }, [focusedIndex]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;

    const handleGlobalKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
      }
    };

    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isEditing, close]);

  return (
    <div {...stylex.props(style)}>
      {label && (
        <div {...stylex.props(styles.labelRow)}>
          <h3 {...stylex.props(styles.label)}>{label}</h3>
          <Button
            variant="icon"
            onClick={open}
            aria-label={`Edit ${label}`}
            style={isEditing && styles.invisible}
          >
            <Pencil {...stylex.props(styles.icon)} />
          </Button>
        </div>
      )}

      <div {...stylex.props(styles.relative, isEditing && styles.raised)}>
        {isEditing ? (
          <div {...stylex.props(styles.draftTags)}>
            {draftTags.map(tag => (
              <Tag
                key={tag}
                action={
                  <Button
                    variant="close"
                    size={null}
                    onClick={() => removeTag(tag)}
                    aria-label={`Remove ${tag}`}
                  >
                    <X {...stylex.props(styles.closeIcon)} />
                  </Button>
                }
              >
                {tag}
              </Tag>
            ))}
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={e => {
                setInputValue(e.target.value);
                setFocusedIndex(-1);
              }}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              {...stylex.props(styles.input)}
            />
          </div>
        ) : displayTags.length > 0 ? (
          <div {...stylex.props(styles.tags)}>
            {displayTags.map(tag => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        ) : (
          <p {...stylex.props(styles.empty)}>{emptyText}</p>
        )}

        {saveError && <p {...stylex.props(styles.error)}>{saveError}</p>}

        {isEditing && (
          <div {...stylex.props(styles.dropdown)}>
            {totalOptions > 0 ? (
              <div {...stylex.props(styles.options)}>
                {showCreateOption && (
                  <button
                    ref={focusedIndex === 0 ? focusedOptionRef : undefined}
                    type="button"
                    onClick={handleCreateTag}
                    disabled={isCreating}
                    {...stylex.props(
                      styles.createOption,
                      focusedIndex === 0 ? styles.highlighted : styles.hovered,
                      isCreating && styles.creating
                    )}
                  >
                    {isCreating ? (
                      <Loader2 {...stylex.props(styles.icon, styles.spinningIcon)} />
                    ) : (
                      <Plus {...stylex.props(styles.icon)} />
                    )}
                    <span {...stylex.props(styles.createLabel)}>
                      Create tag "{trimmedInput}"
                    </span>
                  </button>
                )}
                {filteredSuggestions.map((suggestion, index) => {
                  const optionIndex = showCreateOption ? index + 1 : index;
                  return (
                    <button
                      ref={optionIndex === focusedIndex ? focusedOptionRef : undefined}
                      key={suggestion}
                      type="button"
                      onClick={() => addTag(suggestion)}
                      {...stylex.props(
                        styles.suggestion,
                        optionIndex === focusedIndex ? styles.highlighted : styles.hovered
                      )}
                    >
                      {suggestion}
                    </button>
                  );
                })}
              </div>
            ) : inputValue.trim() ? (
              <div {...stylex.props(styles.noMatches)}>
                <p {...stylex.props(!allowTagCreation && styles.emptyMessage)}>
                  No tags match that query.
                </p>
                {!allowTagCreation && (
                  <p>
                    If you think we need a new tag, come ask in <GetHelpLink />.
                  </p>
                )}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {isEditing && (
        <div {...stylex.props(styles.backdrop)} aria-hidden="true" onClick={close} />
      )}
    </div>
  );
}

const spin = stylex.keyframes({to: {transform: 'rotate(360deg)'}});
const styles = stylex.create({
  spinningIcon: {
    animationName: spin,
    animationDuration: '1s',
    animationTimingFunction: 'linear',
    animationIterationCount: 'infinite',
  },
  labelRow: {
    marginBottom: space.md,
    gap: space.xs,
    display: 'flex',
    alignItems: 'center',
  },
  label: {fontSize: fontSize.md, color: content.secondary, fontWeight: 600},
  icon: {height: 16, width: 16},
  draftTags: {gap: space.sm, display: 'flex', flexWrap: 'wrap', alignItems: 'center'},
  closeIcon: {height: 14, width: 14},
  input: {
    paddingInline: space.sm,
    paddingBlock: space.xs,
    fontSize: fontSize.sm,
    color: {default: null, '::placeholder': content.disabled},
    minWidth: '100px',
    flex: '1',
    backgroundColor: 'transparent',
  },
  tags: {gap: space.sm, display: 'flex', flexWrap: 'wrap'},
  empty: {fontSize: fontSize.sm, color: content.disabled, fontStyle: 'italic'},
  error: {fontSize: fontSize.sm, color: content.danger, marginTop: space.sm},
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
    display: {default: null, '::-webkit-scrollbar': 'none'},
  },
  createLabel: {marginTop: '1px', marginBottom: 'auto'},
  noMatches: {
    fontSize: fontSize.sm,
    color: content.secondary,
    paddingInline: space.md,
    paddingBlock: space.lg,
    textAlign: 'center',
  },
  backdrop: {position: 'fixed', inset: 0, zIndex: 40, backgroundColor: 'transparent'},
  invisible: {visibility: 'hidden'},
  relative: {position: 'relative'},
  raised: {zIndex: 50},
  emptyMessage: {marginBottom: space.sm},
  createOption: {
    width: '100%',
    textAlign: 'left',
    paddingInline: space.md,
    paddingBlock: space.sm,
    cursor: 'pointer',
    borderRadius: radius.sm,
    fontSize: fontSize.sm,
    display: 'flex',
    alignItems: 'center',
    gap: space.sm,
  },
  highlighted: {backgroundColor: background.secondary},
  hovered: {
    backgroundColor: {default: null, ':hover': background.transparentNeutralMuted},
  },
  creating: {cursor: 'wait', opacity: 0.7},
  suggestion: {
    width: '100%',
    textAlign: 'left',
    paddingInline: space.md,
    paddingBlock: space.sm,
    cursor: 'pointer',
    borderRadius: radius.sm,
    fontSize: fontSize.sm,
  },
});
