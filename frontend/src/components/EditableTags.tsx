import {useEffect, useRef, useState} from 'react';
import {cva} from 'class-variance-authority';
import {Pencil, X} from 'lucide-react';
import {cn} from 'utils/cn';

import {Spinner} from './Spinner';
import {Tag} from './Tag';

const buttonBaseStyles = [
  'inline-flex',
  'items-center',
  'justify-center',
  'px-space-md',
  'py-space-sm',
  'rounded-radius-md',
  'font-medium',
  'text-sm',
  'transition-colors',
  'disabled:opacity-50',
  'disabled:cursor-not-allowed',
];

const saveButtonStyles = cva([
  ...buttonBaseStyles,
  'bg-background-accent-vibrant',
  'text-content-on-vibrant-light',
  'hover:opacity-90',
  'w-16',
  'h-8',
]);

const cancelButtonStyles = cva([
  ...buttonBaseStyles,
  'bg-background-secondary',
  'text-content-primary',
  'hover:bg-background-tertiary',
  'w-16',
  'h-8',
]);

export interface EditableTagsProps {
  tags: string[];
  onSave: (tags: string[]) => Promise<void>;
  onCreate?: (name: string) => Promise<void>;
  label?: string;
  suggestions?: string[];
  placeholder?: string;
  emptyText?: string;
  className?: string;
}

export function EditableTags({
  tags,
  onSave,
  onCreate,
  label,
  suggestions = [],
  placeholder = 'Add...',
  emptyText = 'None specified',
  className,
}: EditableTagsProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftTags, setDraftTags] = useState<string[]>(tags);
  const [inputValue, setInputValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const resetState = () => {
    setInputValue('');
    setFocusedIndex(-1);
  };

  const open = () => {
    setDraftTags(tags);
    setIsEditing(true);
    setError(null);
    resetState();
  };

  const cancel = () => {
    setIsEditing(false);
    setDraftTags(tags);
    resetState();
  };

  const save = async () => {
    setIsSaving(true);
    try {
      await onSave(draftTags);
      setIsEditing(false);
      resetState();
    } catch (err) {
      console.error('Failed to save:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const filteredSuggestions = suggestions.filter(
    s => !draftTags.includes(s) && s.toLowerCase().includes(inputValue.toLowerCase())
  );

  const showCreateOption =
    inputValue.trim() &&
    !draftTags.includes(inputValue.trim()) &&
    !suggestions.some(s => s.toLowerCase() === inputValue.trim().toLowerCase());

  const totalOptions = filteredSuggestions.length + (showCreateOption ? 1 : 0);

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !draftTags.includes(trimmed)) {
      setDraftTags(prev => [...prev, trimmed]);
      resetState();
      inputRef.current?.focus();
    }
  };

  const createTag = async (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !draftTags.includes(trimmed)) {
      setError(null);
      try {
        if (onCreate) {
          await onCreate(trimmed);
        }
        addTag(trimmed);
      } catch {
        setError(`Failed to create "${trimmed}"`);
      }
    }
  };

  const removeTag = (tag: string) => {
    setDraftTags(prev => prev.filter(t => t !== tag));
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
        if (focusedIndex >= 0 && focusedIndex < filteredSuggestions.length) {
          addTag(filteredSuggestions[focusedIndex]);
        } else if (
          showCreateOption &&
          (focusedIndex === filteredSuggestions.length || focusedIndex === -1)
        ) {
          createTag(inputValue);
        } else if (!inputValue.trim()) {
          save();
        }
        break;
      case ' ':
        if (focusedIndex >= 0) {
          event.preventDefault();
          if (focusedIndex < filteredSuggestions.length) {
            addTag(filteredSuggestions[focusedIndex]);
          } else if (showCreateOption) {
            createTag(inputValue);
          }
        }
        break;
      case 'Escape':
        event.preventDefault();
        cancel();
        break;
      case 'Backspace':
        if (inputValue === '' && draftTags.length > 0) {
          removeTag(draftTags[draftTags.length - 1]);
        }
        break;
    }
  };

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  return (
    <div className={className}>
      {label && (
        <div className="mb-space-md flex items-center gap-space-xs">
          <h3 className="text-size-md font-semibold text-content-secondary">{label}</h3>
          <button
            type="button"
            onClick={open}
            aria-label={`Edit ${label}`}
            className={cn(
              'inline-flex items-center justify-center p-space-xs rounded-radius-sm',
              'hover:bg-background-secondary hover:scale-110 transition-all cursor-pointer',
              'text-content-secondary hover:text-content-primary',
              isEditing && 'invisible'
            )}
          >
            <Pencil className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="flex flex-wrap items-center gap-space-sm">
            {draftTags.map(tag => (
              <Tag
                key={tag}
                action={
                  <button
                    onClick={() => removeTag(tag)}
                    className="text-content-disabled hover:text-content-primary transition-colors cursor-pointer"
                    aria-label={`Remove ${tag}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
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
              className="min-w-[100px] flex-1 px-space-sm py-space-xs text-size-sm bg-transparent placeholder:text-content-disabled focus:outline-none"
            />
          </div>
        ) : tags.length > 0 ? (
          <div className="flex flex-wrap gap-space-sm">
            {tags.map(tag => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">{emptyText}</p>
        )}

        {isEditing && (
          <div className="absolute left-0 right-0 z-50 mt-space-xs rounded-radius-md border border-gray-200 bg-background-primary shadow-lg">
            {(filteredSuggestions.length > 0 || showCreateOption) && (
              <div className="max-h-[200px] overflow-y-auto p-space-sm [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                {filteredSuggestions.map((suggestion, index) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => addTag(suggestion)}
                    className={cn(
                      'w-full text-left px-space-md py-space-sm cursor-pointer rounded-radius-sm text-size-sm',
                      index === focusedIndex
                        ? 'bg-background-secondary'
                        : 'hover:bg-background-tertiary'
                    )}
                  >
                    {suggestion}
                  </button>
                ))}
                {showCreateOption && (
                  <button
                    type="button"
                    onClick={() => createTag(inputValue)}
                    className={cn(
                      'w-full text-left px-space-md py-space-sm cursor-pointer rounded-radius-sm text-size-sm text-content-accent',
                      focusedIndex === filteredSuggestions.length
                        ? 'bg-background-secondary'
                        : 'hover:bg-background-tertiary'
                    )}
                  >
                    Create "{inputValue.trim()}"
                  </button>
                )}
              </div>
            )}
            {error && (
              <p className="text-content-danger px-space-sm pt-space-sm text-size-sm">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-space-sm p-space-sm border-t border-gray-200">
              <button
                type="button"
                onClick={save}
                disabled={isSaving}
                className={cn(saveButtonStyles())}
              >
                {isSaving ? <Spinner size="sm" /> : 'Save'}
              </button>
              <button
                type="button"
                onClick={cancel}
                disabled={isSaving}
                className={cn(cancelButtonStyles())}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {isEditing && (
        <div
          className="fixed inset-0 z-40 bg-transparent"
          aria-hidden="true"
          onClick={cancel}
        />
      )}
    </div>
  );
}
