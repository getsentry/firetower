import React, {useCallback, useEffect, useRef, useState} from 'react';
import {cva} from 'class-variance-authority';
import {Pencil} from 'lucide-react';
import {cn} from 'utils/cn';
import {z} from 'zod';

import {Spinner} from './Spinner';

const displayContainerStyles = cva(['flex', 'items-center', 'gap-space-xs']);

const displayStyles = cva(['transition-opacity'], {
  variants: {
    editing: {
      true: ['hidden'],
      false: [],
    },
  },
});

// Label layout styles
const labelContainerStyles = cva(['flex', 'items-center', 'gap-space-xs', 'mb-space-xs']);

const labelStyles = cva(['font-medium', 'text-content-secondary', 'text-sm']);

const triggerStyles = cva(
  [
    'inline-flex',
    'items-center',
    'justify-center',
    'transition-all',
    'p-space-xs',
    'rounded-radius-sm',
    'hover:bg-background-secondary',
    'hover:scale-110',
    'focus:outline-none',
    'focus:ring-2',
    'focus:ring-offset-2',
    'text-content-secondary',
    'hover:text-content-primary',
    'cursor-pointer',
    'my-auto',
  ],
  {
    variants: {
      hidden: {
        true: ['hidden'],
        false: [],
      },
    },
  }
);

const inputStyles = cva(
  [
    'w-full',
    'px-space-md',
    'py-space-sm',
    'rounded-radius-md',
    'border-2',
    'border-border-primary',
    'focus:border-content-accent',
    'focus:outline-none',
    'text-content-primary',
    'bg-background-primary',
    'transition-colors',
    'm-0',
  ],
  {
    variants: {
      error: {
        true: ['border-content-danger', 'focus:border-content-danger'],
        false: [],
      },
      hidden: {
        true: ['hidden'],
        false: [],
      },
    },
  }
);

const actionsStyles = cva(['flex', 'items-center', 'gap-space-sm'], {
  variants: {
    hidden: {
      true: ['hidden'],
      false: [],
    },
  },
});

const buttonBaseStyles = [
  'inline-flex',
  'items-center',
  'justify-center',
  'gap-space-xs',
  'px-space-md',
  'py-space-sm',
  'rounded-radius-md',
  'font-medium',
  'text-sm',
  'transition-colors',
  'focus:outline-auto',
  'disabled:opacity-50',
  'disabled:cursor-not-allowed',
];

const saveButtonStyles = cva([
  ...buttonBaseStyles,
  'bg-background-accent-vibrant',
  'text-content-on-vibrant-light',
  'hover:opacity-90',
  'hover:scale-105',
  'active:scale-95',
  'disabled:hover:opacity-50',
  'disabled:hover:scale-100',
  'w-16', // Fixed width to prevent layout shift
  'h-8', // Fixed height to prevent layout shift
]);

const cancelButtonStyles = cva([
  ...buttonBaseStyles,
  'bg-background-secondary',
  'text-content-primary',
  'hover:bg-background-tertiary',
  'hover:scale-105',
  'active:scale-95',
  'w-16', // Fixed width to match save button
  'h-8', // Fixed height to match save button
]);

const messageStyles = cva(['text-sm', 'mt-space-xs'], {
  variants: {
    type: {
      error: ['text-content-danger'],
      success: ['text-content-success'],
    },
  },
});

export interface EditableTextFieldProps {
  // Required
  value: string;
  onSave: (newValue: string) => Promise<void>;

  // Optional
  as?: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  validationSchema?: z.ZodSchema<string>;
  multiline?: boolean;
  fullWidth?: boolean; // Whether display text should expand to full width (default: false)
  className?: string;

  // Label layout (if present, pencil appears next to label instead of value)
  label?: string;
  labelAs?: 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  labelClassName?: string;
}

export function EditableTextField({
  value,
  onSave,
  as: Component = 'div',
  validationSchema,
  multiline = false,
  fullWidth = false,
  className,
  label,
  labelAs: LabelComponent = 'div',
  labelClassName,
}: EditableTextFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const startEditing = useCallback(() => {
    setIsEditing(true);
    setError(null);
    setValidationError(null);
    setDraftValue(value);
  }, [value]);

  const cancelEditing = useCallback(() => {
    setIsEditing(false);
    setDraftValue(value);
    setError(null);
    setValidationError(null);
  }, [value]);

  const save = useCallback(async () => {
    // Clear previous errors
    setError(null);
    setValidationError(null);

    // Client-side validation with Zod
    if (validationSchema) {
      const result = validationSchema.safeParse(draftValue);
      if (!result.success) {
        setValidationError(result.error.issues[0].message);
        return;
      }
    }

    // Don't save if value hasn't changed
    if (draftValue === value) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);

    try {
      await onSave(draftValue);

      // Exit edit mode immediately on success
      setIsEditing(false);
    } catch (err) {
      // Show error and stay in edit mode
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsSaving(false);
    }
  }, [validationSchema, draftValue, value, onSave]);

  const updateDraft = useCallback((newValue: string) => {
    setDraftValue(newValue);
    setValidationError(null);
  }, []);

  // Update draft when value changes (e.g., after successful save)
  useEffect(() => {
    if (!isEditing) {
      setDraftValue(value);
    }
  }, [value, isEditing]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      // Place cursor at end of text
      const length = inputRef.current.value.length;
      inputRef.current.setSelectionRange(length, length);
    }
  }, [isEditing]);

  // Handle keyboard shortcuts
  useEffect(() => {
    if (!isEditing) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Enter to save (only for single-line, or Ctrl/Cmd+Enter for multiline)
      if (event.key === 'Enter') {
        if (!multiline || event.ctrlKey || event.metaKey) {
          event.preventDefault();
          save();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isEditing, multiline, save]);

  // Auto-resize textarea to fit content
  useEffect(() => {
    if (multiline && inputRef.current && isEditing) {
      const textarea = inputRef.current as HTMLTextAreaElement;
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';
      // Set height to scrollHeight to fit content
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [draftValue, multiline, isEditing]);

  const hasError = !!validationError;
  const errorMessage = validationError || error;

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    updateDraft(e.target.value);
    // Auto-resize on change
    if (multiline) {
      const textarea = e.target as HTMLTextAreaElement;
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  };

  return (
    <div className="relative">
      {label ? (
        // Label layout: Pencil next to label, value separate
        <>
          {/* Label + Trigger (always visible) */}
          <div className={cn(labelContainerStyles())}>
            <LabelComponent className={cn(labelStyles(), labelClassName)}>
              {label}
            </LabelComponent>
            {!isEditing && (
              <button
                type="button"
                onClick={startEditing}
                aria-label="Edit"
                className={cn(triggerStyles({hidden: false}))}
              >
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Display Value (no pencil) */}
          {!isEditing && <Component className={cn(className)}>{value}</Component>}
        </>
      ) : (
        // Default layout: Pencil next to value
        <div
          className={cn(displayContainerStyles(), displayStyles({editing: isEditing}))}
        >
          <Component className={cn(fullWidth ? 'flex-1 min-w-0' : 'inline', className)}>
            {value}
          </Component>
          {!isEditing && (
            <button
              type="button"
              onClick={startEditing}
              aria-label="Edit"
              className={cn(triggerStyles({hidden: isEditing}))}
            >
              <Pencil className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Input + Actions */}
      {isEditing && (
        <>
          {multiline || label ? (
            // Multiline or labeled: Stack vertically with actions below
            <>
              {multiline ? (
                <textarea
                  ref={inputRef as React.RefObject<HTMLTextAreaElement>}
                  value={draftValue}
                  onChange={handleInputChange}
                  className={cn(
                    inputStyles({error: hasError, hidden: !isEditing}),
                    className
                  )}
                  autoFocus
                  aria-invalid={hasError}
                  style={{
                    minHeight: '80px',
                    resize: 'none',
                    overflow: 'hidden',
                  }}
                />
              ) : (
                <input
                  ref={inputRef as React.RefObject<HTMLInputElement>}
                  type="text"
                  value={draftValue}
                  onChange={handleInputChange}
                  className={cn(
                    inputStyles({error: hasError, hidden: !isEditing}),
                    className
                  )}
                  autoFocus
                  aria-invalid={hasError}
                />
              )}
              <div className={cn(actionsStyles({hidden: !isEditing}), 'mt-space-sm')}>
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
                  onClick={cancelEditing}
                  disabled={isSaving}
                  className={cn(cancelButtonStyles())}
                >
                  Cancel
                </button>
              </div>
            </>
          ) : (
            // Single-line without label: Inline with buttons
            <div className="gap-space-sm flex items-center">
              <input
                ref={inputRef as React.RefObject<HTMLInputElement>}
                type="text"
                value={draftValue}
                onChange={handleInputChange}
                className={cn(
                  inputStyles({error: hasError, hidden: !isEditing}),
                  className
                )}
                autoFocus
                aria-invalid={hasError}
              />
              <div className={cn(actionsStyles({hidden: !isEditing}))}>
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
                  onClick={cancelEditing}
                  disabled={isSaving}
                  className={cn(cancelButtonStyles())}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <div
              role="alert"
              aria-live="polite"
              className={cn(messageStyles({type: 'error'}), 'mt-space-xs')}
            >
              {errorMessage}
            </div>
          )}
        </>
      )}
    </div>
  );
}
