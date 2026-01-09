import React, {useEffect, useRef} from 'react';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

import {Button} from './Button';

const overlay = cva(['fixed', 'inset-0', 'z-50', 'bg-black/50']);

const dialog = cva([
  'fixed',
  'top-1/2',
  'left-1/2',
  '-translate-x-1/2',
  '-translate-y-1/2',
  'z-50',
  'w-full',
  'max-w-md',
  'rounded-radius-lg',
  'bg-background-primary',
  'p-space-2xl',
  'shadow-xl',
]);

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

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      <div className={cn(overlay())} onClick={onCancel} aria-hidden="true" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={cn(dialog())}
      >
        <h2
          id="dialog-title"
          className="mb-space-md text-content-headings text-lg font-semibold"
        >
          {title}
        </h2>
        <div className="mb-space-xl text-content-secondary">{message}</div>
        <div className="gap-space-md flex justify-end">
          <Button variant="primary" onClick={onConfirm} className="w-auto">
            {confirmLabel}
          </Button>
          <Button variant="secondary" onClick={onCancel} className="w-auto">
            {cancelLabel}
          </Button>
        </div>
      </div>
    </>
  );
}

export {ConfirmationDialog, type ConfirmationDialogProps};
