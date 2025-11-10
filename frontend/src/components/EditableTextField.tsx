import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {cva} from 'class-variance-authority';
import {Pencil} from 'lucide-react';
import {cn} from 'utils/cn';
import {z} from 'zod';

import {Spinner} from './Spinner';

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

const rootStyles = cva(['relative', 'group'], {
  variants: {
    editing: {
      true: [],
      false: [],
    },
  },
});

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

  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const startEditing = useCallback(() => {
    if (!editable) return;
    setIsEditing(true);
    setError(null);
    setValidationError(null);
    setDraftValue(value);
  }, [editable, value]);

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

  const updateDraft = useCallback(
    (newValue: string) => {
      setDraftValue(newValue);
      // Clear validation error when user starts typing
      if (validationError) {
        setValidationError(null);
      }
    },
    [validationError]
  );

  const contextValue: EditableTextFieldContextValue = useMemo(
    () => ({
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
      inputRef,
    }),
    [
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
      inputRef,
    ]
  );

  return (
    <EditableTextFieldContext.Provider value={contextValue}>
      <div className={cn(rootStyles({editing: isEditing}), className)}>{children}</div>
    </EditableTextFieldContext.Provider>
  );
}

const displayStyles = cva(['transition-opacity'], {
  variants: {
    editing: {
      true: ['hidden'],
      false: ['block'],
    },
  },
});

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

function Input({
  className,
  ...props
}: Omit<
  React.InputHTMLAttributes<HTMLInputElement> &
    React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  'ref'
>) {
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
    autoFocus: true,
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

function Actions({className, ...props}: React.HTMLAttributes<HTMLDivElement>) {
  const {isEditing, save, cancelEditing, isSaving, error, validationError} =
    useEditableTextField();

  if (!isEditing) return null;

  const errorMessage = validationError || error;

  return (
    <>
      <div className={cn(actionsStyles({hidden: !isEditing}), className)} {...props}>
        <button
          type="button"
          onClick={save}
          disabled={isSaving}
          className={cn(saveButtonStyles())}
        >
          {isSaving ? (
            <>
              <Spinner size="sm" />
              <span>Saving...</span>
            </>
          ) : (
            'Save'
          )}
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
      {errorMessage && (
        <div
          role="alert"
          aria-live="polite"
          className={cn(messageStyles({type: 'error', hidden: false}), 'mt-space-xs')}
        >
          {errorMessage}
        </div>
      )}
    </>
  );
}

export const EditableTextField = Object.assign(EditableTextFieldRoot, {
  Display,
  Trigger,
  Input,
  Actions,
});

export type {EditableTextFieldRootProps, DisplayProps, TriggerProps};
