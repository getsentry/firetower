import React, {useEffect, useRef} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useBodyScrollLock} from 'utils/useBodyScrollLock';

import {background, content, radius, space} from '../styles/tokens.stylex';

import {Button} from './Button';

interface ConfirmationDialogProps {
  isOpen: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function ConfirmationDialog({
  isOpen,
  title,
  message,
  confirmLabel,
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onCancel]);

  useBodyScrollLock(isOpen);

  if (!isOpen) return null;

  return (
    <>
      <div {...stylex.props(styles.overlay)} onClick={onCancel} aria-hidden="true" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        {...stylex.props(styles.dialog)}
      >
        <h2 id="dialog-title" {...stylex.props(styles.title)}>
          {title}
        </h2>
        <div {...stylex.props(styles.message)}>{message}</div>
        <div {...stylex.props(styles.actions)}>
          <Button variant="secondary" onClick={onCancel} style={styles.autoWidth}>
            {cancelLabel}
          </Button>
          <Button variant="primary" onClick={onConfirm} style={styles.autoWidth}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </>
  );
}

export {ConfirmationDialog, type ConfirmationDialogProps};

const styles = stylex.create({
  overlay: {position: 'fixed', inset: 0, zIndex: 50, backgroundColor: 'rgb(0 0 0 / 0.5)'},
  dialog: {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    zIndex: 50,
    width: '100%',
    maxWidth: 448,
    borderRadius: radius.lg,
    backgroundColor: background.primary,
    padding: space['2xl'],
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  },
  title: {
    marginBottom: space.md,
    color: content.headings,
    fontSize: 18,
    lineHeight: '28px',
    fontWeight: 600,
  },
  message: {marginBottom: space.xl, color: content.secondary},
  actions: {gap: space.md, display: 'flex', justifyContent: 'flex-end'},
  autoWidth: {width: 'auto'},
});
