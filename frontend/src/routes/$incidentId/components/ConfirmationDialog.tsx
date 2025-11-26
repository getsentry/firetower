import {useEffect, useRef} from 'react';
import {cva} from 'class-variance-authority';
import {cn} from 'utils/cn';

const overlayStyles = cva(['fixed', 'inset-0', 'z-50', 'bg-black/50']);

const dialogStyles = cva([
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

const buttonStyles = cva(
  [
    'px-space-xl',
    'py-space-md',
    'rounded-radius-md',
    'text-sm',
    'font-medium',
    'transition-colors',
  ],
  {
    variants: {
      variant: {
        primary: ['bg-gray-900', 'text-white', 'hover:bg-gray-800'],
        secondary: ['bg-gray-100', 'text-gray-900', 'hover:bg-gray-200'],
      },
    },
  }
);

interface ConfirmationDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmationDialog({
  isOpen,
  title,
  message,
  confirmLabel,
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
      <div className={cn(overlayStyles())} onClick={onCancel} aria-hidden="true" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={cn(dialogStyles())}
      >
        <h2
          id="dialog-title"
          className="text-content-headings mb-space-md text-lg font-semibold"
        >
          {title}
        </h2>
        <p className="text-content-secondary mb-space-xl">{message}</p>
        <div className="gap-space-md flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            className={cn(buttonStyles({variant: 'secondary'}))}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={cn(buttonStyles({variant: 'primary'}))}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </>
  );
}
