import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import {cva} from 'class-variance-authority';
import {Pencil} from 'lucide-react';
import {cn} from 'utils/cn';
import {z} from 'zod';

import {Spinner} from './Spinner';

// ============================================================================
// Context
// ============================================================================

interface EditableTextFieldContextValue {
  // State
  value: string;
  draftValue: string;
  isEditing: boolean;
  isSaving: boolean;
  error: string | null;
  validationError: string | null;

  // Actions
  startEditing: () => void;
  cancelEditing: () => void;
  save: () => Promise<void>;
  updateDraft: (value: string) => void;

  // Config
  editable: boolean;
  multiline: boolean;

  // Refs
  rootRef: React.RefObject<HTMLDivElement | null>;
  inputRef: React.RefObject<HTMLInputElement | HTMLTextAreaElement | null>;
}

const EditableTextFieldContext = createContext<EditableTextFieldContextValue | null>(
  null
);

function useEditableTextField() {
  const context = useContext(EditableTextFieldContext);
  if (!context) {
    throw new Error(
      'EditableTextField subcomponents must be used within EditableTextField.Root'
    );
  }
  return context;
}

// ============================================================================
// Styles
// ============================================================================

const rootStyles = cva(['relative', 'group'], {
  variants: {
    editing: {
      true: [],
      false: [],
    },
  },
});

const displayStyles = cva(['transition-opacity'], {
  variants: {
    editing: {
      true: ['hidden'],
      false: ['block'],
    },
  },
});

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
  'focus:outline-none',
  'focus:ring-2',
  'focus:ring-offset-2',
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
]);

const cancelButtonStyles = cva([
  ...buttonBaseStyles,
  'bg-background-secondary',
  'text-content-primary',
  'hover:bg-background-tertiary',
  'hover:scale-105',
  'active:scale-95',
]);

const messageStyles = cva(['text-sm', 'mt-space-xs'], {
  variants: {
    type: {
      error: ['text-content-danger'],
      success: ['text-content-success'],
    },
    hidden: {
      true: ['hidden'],
      false: [],
    },
  },
});

// ============================================================================
// Root Component
// ============================================================================

interface EditableTextFieldRootProps {
  // Required
  value: string;
  onSave: (newValue: string) => Promise<void>;

  // Optional
  editable?: boolean;
  validationSchema?: z.ZodSchema<string>;
  multiline?: boolean;

  // Styling
  className?: string;
  children: React.ReactNode;
}

function EditableTextFieldRoot({
  value,
  onSave,
  editable = true,
  validationSchema,
  multiline = false,
  className,
  children,
}: EditableTextFieldRootProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const startEditing = useCallback(() => {
    if (!editable) return;
    setIsEditing(true);
    setError(null);
    setValidationError(null);
    setDraftValue(value);
  }, [editable, value]);

  const cancelEditing = useCallback(() => {
    // Show confirmation if value has changed
    if (draftValue !== value) {
      const confirmed = window.confirm(
        'You have unsaved changes. Are you sure you want to discard them?'
      );
      if (!confirmed) return;
    }

    setIsEditing(false);
    setDraftValue(value);
    setError(null);
    setValidationError(null);
  }, [draftValue, value]);

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

  // Handle click outside
  useEffect(() => {
    if (!isEditing) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        cancelEditing();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isEditing, cancelEditing]);

  // Handle keyboard shortcuts
  useEffect(() => {
    if (!isEditing) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // ESC to cancel
      if (event.key === 'Escape') {
        event.preventDefault();
        cancelEditing();
      }
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
  }, [isEditing, multiline, cancelEditing, save]);

  const updateDraft = (newValue: string) => {
    setDraftValue(newValue);
    // Clear validation error when user starts typing
    if (validationError) {
      setValidationError(null);
    }
  };

  const contextValue: EditableTextFieldContextValue = {
    value,
    draftValue,
    isEditing,
    isSaving,
    error,
    validationError,
    startEditing,
    cancelEditing,
    save,
    updateDraft,
    editable,
    multiline,
    rootRef,
    inputRef,
  };

  return (
    <EditableTextFieldContext.Provider value={contextValue}>
      <div ref={rootRef} className={cn(rootStyles({editing: isEditing}), className)}>
        {children}
      </div>
    </EditableTextFieldContext.Provider>
  );
}

// ============================================================================
// Display Component
// ============================================================================

interface DisplayProps extends React.HTMLAttributes<HTMLElement> {
  as?: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  children: React.ReactNode;
}

function Display({as: Component = 'div', className, children, ...props}: DisplayProps) {
  const {isEditing} = useEditableTextField();

  return (
    <Component className={cn(displayStyles({editing: isEditing}), className)} {...props}>
      {children}
    </Component>
  );
}

// ============================================================================
// Trigger Component
// ============================================================================

interface TriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children?: React.ReactNode;
}

function Trigger({className, children, ...props}: TriggerProps) {
  const {startEditing, editable, isEditing} = useEditableTextField();

  if (!editable || isEditing) return null;

  return (
    <button
      type="button"
      onClick={startEditing}
      aria-label="Edit"
      className={cn(triggerStyles({hidden: isEditing}), className)}
      {...props}
    >
      {children || <Pencil className="h-4 w-4" />}
    </button>
  );
}

// ============================================================================
// Input Component
// ============================================================================

interface InputProps
  extends Omit<
    React.InputHTMLAttributes<HTMLInputElement> &
      React.TextareaHTMLAttributes<HTMLTextAreaElement>,
    'ref'
  > {
  autoFocus?: boolean;
  rows?: number;
}

function Input({className, autoFocus = true, ...props}: InputProps) {
  const {draftValue, updateDraft, isEditing, multiline, validationError, inputRef} =
    useEditableTextField();

  const hasError = !!validationError;

  // Auto-resize textarea to fit content
  useEffect(() => {
    if (multiline && inputRef.current && isEditing) {
      const textarea = inputRef.current as HTMLTextAreaElement;
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';
      // Set height to scrollHeight to fit content
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [draftValue, multiline, isEditing, inputRef]);

  if (!isEditing) return null;

  const commonProps = {
    ref: inputRef as React.RefObject<HTMLInputElement | HTMLTextAreaElement>,
    value: draftValue,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      updateDraft(e.target.value);
      // Auto-resize on change
      if (multiline) {
        const textarea = e.target as HTMLTextAreaElement;
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
      }
    },
    className: cn(inputStyles({error: hasError, hidden: !isEditing}), className),
    autoFocus,
    'aria-invalid': hasError,
    ...props,
  };

  if (multiline) {
    return (
      <textarea
        {...(commonProps as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
        style={{
          minHeight: '80px',
          resize: 'none',
          overflow: 'hidden',
          ...(props.style || {}),
        }}
      />
    );
  }

  return (
    <input
      type="text"
      {...(commonProps as React.InputHTMLAttributes<HTMLInputElement>)}
    />
  );
}

// ============================================================================
// Actions Container
// ============================================================================

interface ActionsProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

function Actions({className, children, ...props}: ActionsProps) {
  const {isEditing} = useEditableTextField();

  return (
    <div className={cn(actionsStyles({hidden: !isEditing}), className)} {...props}>
      {children}
    </div>
  );
}

// ============================================================================
// Save Button
// ============================================================================

interface SaveProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children?: React.ReactNode;
}

function Save({className, children, ...props}: SaveProps) {
  const {save, isSaving} = useEditableTextField();

  return (
    <button
      type="button"
      onClick={save}
      disabled={isSaving}
      className={cn(saveButtonStyles(), className)}
      {...props}
    >
      {isSaving ? (
        <>
          <Spinner size="sm" />
          <span>Saving...</span>
        </>
      ) : (
        children || 'Save'
      )}
    </button>
  );
}

// ============================================================================
// Cancel Button
// ============================================================================

interface CancelProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children?: React.ReactNode;
}

function Cancel({className, children, ...props}: CancelProps) {
  const {cancelEditing, isSaving} = useEditableTextField();

  return (
    <button
      type="button"
      onClick={cancelEditing}
      disabled={isSaving}
      className={cn(cancelButtonStyles(), className)}
      {...props}
    >
      {children || 'Cancel'}
    </button>
  );
}

// ============================================================================
// Error Message
// ============================================================================

interface ErrorMessageProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children'> {
  children?: (error: string) => React.ReactNode;
}

function ErrorMessage({className, children, ...props}: ErrorMessageProps) {
  const {error, validationError} = useEditableTextField();

  const errorMessage = validationError || error;
  if (!errorMessage) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(messageStyles({type: 'error', hidden: !errorMessage}), className)}
      {...props}
    >
      {children ? children(errorMessage) : errorMessage}
    </div>
  );
}

// ============================================================================
// Success Message
// ============================================================================

interface SuccessProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

function Success() {
  // Success indicator disabled - component exits edit mode immediately on save
  return null;
}

// ============================================================================
// Exports
// ============================================================================

export const EditableTextField = Object.assign(EditableTextFieldRoot, {
  Display,
  Trigger,
  Input,
  Actions,
  Save,
  Cancel,
  Error: ErrorMessage,
  Success,
});

export type {
  EditableTextFieldRootProps,
  DisplayProps,
  TriggerProps,
  InputProps,
  ActionsProps,
  SaveProps,
  CancelProps,
  ErrorMessageProps,
  SuccessProps,
};
