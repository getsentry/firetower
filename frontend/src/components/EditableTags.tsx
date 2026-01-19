import {useCallback, useEffect, useRef, useState} from 'react';
import {Pencil, X} from 'lucide-react';
import {cn} from 'utils/cn';

import {Button} from './Button';
import {GetHelpLink} from './GetHelpLink';
import {Tag} from './Tag';

export interface EditableTagsProps {
  tags: string[];
  onSave: (tags: string[]) => Promise<void>;
  label?: string;
  suggestions?: string[];
  placeholder?: string;
  emptyText?: string;
  className?: string;
}

export function EditableTags({
  tags,
  onSave,
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
  const inputRef = useRef<HTMLInputElement>(null);

  const resetState = () => {
    setInputValue('');
    setFocusedIndex(-1);
  };

  const open = () => {
    setDraftTags([...tags].sort((a, b) => a.localeCompare(b)));
    setIsEditing(true);
    resetState();
  };

  const cancel = useCallback(() => {
    setIsEditing(false);
    setDraftTags(tags);
    resetState();
  }, [tags]);

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

  const addTag = (tag: string) => {
    const trimmed = tag.trim();
    if (trimmed && !draftTags.includes(trimmed)) {
      setDraftTags(prev => [...prev, trimmed].sort((a, b) => a.localeCompare(b)));
      resetState();
      inputRef.current?.focus();
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
        if (filteredSuggestions.length > 0) {
          setFocusedIndex(prev => (prev + 1) % filteredSuggestions.length);
        }
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (filteredSuggestions.length > 0) {
          setFocusedIndex(
            prev => (prev - 1 + filteredSuggestions.length) % filteredSuggestions.length
          );
        }
        break;
      case 'Enter':
        event.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < filteredSuggestions.length) {
          addTag(filteredSuggestions[focusedIndex]);
        } else if (!inputValue.trim()) {
          save();
        }
        break;
      case ' ':
        if (focusedIndex >= 0 && focusedIndex < filteredSuggestions.length) {
          event.preventDefault();
          addTag(filteredSuggestions[focusedIndex]);
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

  useEffect(() => {
    if (!isEditing) return;

    const handleGlobalKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancel();
      }
    };

    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => document.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isEditing, cancel]);

  return (
    <div className={className}>
      {label && (
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
      )}

      <div className={cn('relative', isEditing && 'z-50')}>
        {isEditing ? (
          <div className="gap-space-sm flex flex-wrap items-center">
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
                    <X className="h-3.5 w-3.5" />
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
              className="px-space-sm py-space-xs text-size-sm placeholder:text-content-disabled min-w-[100px] flex-1 bg-transparent focus:outline-none"
            />
          </div>
        ) : tags.length > 0 ? (
          <div className="gap-space-sm flex flex-wrap">
            {tags.map(tag => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        ) : (
          <p className="text-size-sm text-content-disabled italic">{emptyText}</p>
        )}

        {isEditing && (
          <div className="mt-space-xs rounded-radius-md bg-background-primary absolute right-0 left-0 z-50 border border-gray-200 shadow-lg">
            {filteredSuggestions.length > 0 ? (
              <div className="p-space-sm max-h-[200px] overflow-y-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                {filteredSuggestions.map((suggestion, index) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => addTag(suggestion)}
                    className={cn(
                      'w-full text-left px-space-md py-space-sm cursor-pointer rounded-radius-sm text-size-sm',
                      index === focusedIndex
                        ? 'bg-background-secondary'
                        : 'hover:bg-background-transparent-neutral-muted'
                    )}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : inputValue.trim() ? (
              <div className="text-size-sm text-content-secondary px-space-md py-space-lg text-center">
                <p className="mb-space-sm">No tags match that query.</p>
                <p>
                  If you think we need a new tag, come ask in <GetHelpLink />.
                </p>
              </div>
            ) : null}
            <div className="gap-space-sm p-space-sm flex justify-end border-t border-gray-200">
              <Button variant="primary" onClick={save} loading={isSaving}>
                Save
              </Button>
              <Button variant="secondary" onClick={cancel} disabled={isSaving}>
                Cancel
              </Button>
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
