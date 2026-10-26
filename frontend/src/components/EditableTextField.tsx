import React, {useCallback, useEffect, useLayoutEffect, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Pencil} from 'lucide-react';
import {z} from 'zod';

import type {StyledProps} from '../styles/props';
import {
  background,
  border,
  content,
  fontWeight,
  radius,
  space,
} from '../styles/tokens.stylex';

import {Button} from './Button';

const styles = stylex.create({
  root: {position: 'relative'},
  displayContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: space.xs,
    transitionProperty: 'opacity',
    transitionDuration: '150ms',
  },
  hidden: {display: 'none'},
  invisible: {visibility: 'hidden'},
  labelContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: space.xs,
    marginBottom: space.md,
  },
  label: {
    fontWeight: fontWeight.medium,
    color: content.secondary,
    fontSize: 14,
    lineHeight: '20px',
  },
  display: {overflowWrap: 'break-word'},
  fullWidth: {flex: '1', minWidth: 0},
  inline: {display: 'inline'},
  multiline: {whiteSpace: 'pre-wrap'},
  placeholder: {color: content.disabled, fontStyle: 'italic'},
  input: {
    width: '100%',
    paddingInline: space.md,
    paddingBlock: space.sm,
    borderRadius: radius.md,
    borderWidth: 2,
    borderStyle: 'solid',
    borderColor: {default: border.primary, ':focus': content.accent},
    color: content.primary,
    backgroundColor: background.primary,
    transitionProperty: 'color, background-color, border-color',
    transitionDuration: '150ms',
    margin: 0,
  },
  invalid: {borderColor: {default: content.danger, ':focus': content.danger}},
  textarea: {minHeight: 80, resize: 'none', overflow: 'hidden'},
  textareaHeight: (height: number | undefined) => ({
    height: height === undefined ? 'auto' : height,
  }),
  actions: {display: 'flex', alignItems: 'center', gap: space.sm},
  stackedActions: {marginTop: space.sm},
  message: {fontSize: 14, lineHeight: '20px', marginTop: space.xs, color: content.danger},
  icon: {width: 16, height: 16},
});

export interface EditableTextFieldProps extends StyledProps<object> {
  value: string;
  onSave: (newValue: string) => Promise<void>;

  as?: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  validationSchema?: z.ZodSchema<string>;
  multiline?: boolean;
  fullWidth?: boolean;
  placeholder?: string;

  label?: string;
  labelAs?: 'h3' | 'h4' | 'h5' | 'h6' | 'span' | 'div';
  labelStyle?: stylex.StyleXStyles;
}

export function EditableTextField({
  value,
  onSave,
  as: Component = 'div',
  validationSchema,
  multiline = false,
  fullWidth = false,
  style,
  placeholder,
  label,
  labelAs: LabelComponent = 'div',
  labelStyle,
}: EditableTextFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [textareaHeight, setTextareaHeight] = useState<number | undefined>();

  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  const startEditing = useCallback(() => {
    setTextareaHeight(undefined);
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
    setError(null);
    setValidationError(null);

    if (validationSchema) {
      const result = validationSchema.safeParse(draftValue);
      if (!result.success) {
        setValidationError(result.error.issues[0].message);
        return;
      }
    }

    if (draftValue === value) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);

    try {
      await onSave(draftValue);

      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsSaving(false);
    }
  }, [validationSchema, draftValue, value, onSave]);

  const updateDraft = useCallback((newValue: string) => {
    setDraftValue(newValue);
    setValidationError(null);
  }, []);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();

      const length = inputRef.current.value.length;
      inputRef.current.setSelectionRange(length, length);
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) return;

    const handleKeyDown = (event: KeyboardEvent) => {
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

  useLayoutEffect(() => {
    if (multiline && isEditing && inputRef.current) {
      setTextareaHeight(inputRef.current.scrollHeight);
    }
  }, [draftValue, multiline, isEditing]);

  const hasError = !!validationError;
  const errorMessage = validationError || error;

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    updateDraft(e.target.value);
    setTextareaHeight(undefined);
  };

  return (
    <div {...stylex.props(styles.root)}>
      {label ? (
        <>
          <div {...stylex.props(styles.labelContainer)}>
            <LabelComponent {...stylex.props(styles.label, labelStyle)}>
              {label}
            </LabelComponent>
            <Button
              variant="icon"
              onClick={startEditing}
              aria-label="Edit"
              style={isEditing && styles.invisible}
            >
              <Pencil {...stylex.props(styles.icon)} />
            </Button>
          </div>
          {!isEditing && (
            <Component
              {...stylex.props(
                styles.display,
                multiline && styles.multiline,
                !value && !!placeholder && styles.placeholder,
                style
              )}
            >
              {value || placeholder}
            </Component>
          )}
        </>
      ) : (
        <div {...stylex.props(styles.displayContainer, isEditing && styles.hidden)}>
          <Component
            {...stylex.props(
              fullWidth ? styles.fullWidth : styles.inline,
              styles.display,
              multiline && styles.multiline,
              !value && !!placeholder && styles.placeholder,
              style
            )}
          >
            {value || placeholder}
          </Component>
          {!isEditing && (
            <Button variant="icon" onClick={startEditing} aria-label="Edit">
              <Pencil {...stylex.props(styles.icon)} />
            </Button>
          )}
        </div>
      )}
      {isEditing && (
        <>
          {multiline || label ? (
            <>
              {multiline ? (
                <textarea
                  ref={inputRef as React.RefObject<HTMLTextAreaElement>}
                  value={draftValue}
                  onChange={handleInputChange}
                  {...stylex.props(
                    styles.input,
                    hasError && styles.invalid,
                    styles.textarea,
                    styles.textareaHeight(textareaHeight),
                    style
                  )}
                  autoFocus
                  aria-invalid={hasError}
                />
              ) : (
                <input
                  ref={inputRef as React.RefObject<HTMLInputElement>}
                  type="text"
                  value={draftValue}
                  onChange={handleInputChange}
                  {...stylex.props(styles.input, hasError && styles.invalid, style)}
                  autoFocus
                  aria-invalid={hasError}
                />
              )}
              <div {...stylex.props(styles.actions, styles.stackedActions)}>
                <Button variant="primary" onClick={save} loading={isSaving}>
                  Save
                </Button>
                <Button variant="secondary" onClick={cancelEditing} disabled={isSaving}>
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <div {...stylex.props(styles.actions)}>
              <input
                ref={inputRef as React.RefObject<HTMLInputElement>}
                type="text"
                value={draftValue}
                onChange={handleInputChange}
                {...stylex.props(styles.input, hasError && styles.invalid, style)}
                autoFocus
                aria-invalid={hasError}
              />
              <div {...stylex.props(styles.actions)}>
                <Button variant="primary" onClick={save} loading={isSaving}>
                  Save
                </Button>
                <Button variant="secondary" onClick={cancelEditing} disabled={isSaving}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
          {errorMessage && (
            <div role="alert" aria-live="polite" {...stylex.props(styles.message)}>
              {errorMessage}
            </div>
          )}
        </>
      )}
    </div>
  );
}
