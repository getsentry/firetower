import {useCallback, useEffect, useRef, useState} from 'react';
import {cva} from 'class-variance-authority';
import {ConfirmationDialog} from 'components/ConfirmationDialog';
import {EllipsisVertical} from 'lucide-react';
import {cn} from 'utils/cn';

const triggerStyles = cva([
  'cursor-pointer',
  'text-content-secondary',
  'hover:text-content-primary',
  'hover:bg-gray-100',
  'rounded-radius-sm',
  'p-space-xs',
  'transition-colors',
]);

const popoverStyles = cva([
  'absolute',
  'z-50',
  'top-full',
  'right-0',
  'mt-space-xs',
  'rounded-radius-md',
  'border',
  'border-gray-200',
  'bg-background-primary',
  'shadow-lg',
  'p-space-sm',
  'min-w-max',
]);

const menuItemStyles = cva([
  'w-full',
  'cursor-pointer',
  'rounded-radius-md',
  'px-space-md',
  'py-space-sm',
  'text-left',
  'text-sm',
  'transition-colors',
  'hover:bg-gray-100',
]);

interface OverflowMenuProps {
  isPrivate: boolean;
  onToggleVisibility: () => Promise<void>;
}

export function OverflowMenu({isPrivate, onToggleVisibility}: OverflowMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setIsOpen(false);
    triggerRef.current?.focus();
  }, []);

  const handleMenuItemClick = useCallback(() => {
    close();
    setShowConfirmation(true);
  }, [close]);

  const handleConfirm = useCallback(async () => {
    setShowConfirmation(false);
    setIsLoading(true);
    try {
      await onToggleVisibility();
    } catch (err) {
      console.error('Failed to toggle visibility:', err);
    } finally {
      setIsLoading(false);
    }
  }, [onToggleVisibility]);

  const handleCancel = useCallback(() => {
    setShowConfirmation(false);
  }, []);

  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node)
      ) {
        close();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, close]);

  const dialogTitle = isPrivate
    ? 'Make incident public?'
    : 'Convert to private incident?';
  const dialogMessage = isPrivate
    ? 'This incident will be visible to all users.'
    : 'This incident will only be visible to participants and admins.';
  const confirmLabel = isPrivate ? 'Make public' : 'Convert to private';

  return (
    <>
      <div className="relative" ref={menuRef}>
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          disabled={isLoading}
          className={cn(triggerStyles())}
          aria-label="More actions"
          aria-expanded={isOpen}
          aria-haspopup="menu"
        >
          <EllipsisVertical className="h-5 w-5" />
        </button>

        {isOpen && (
          <div role="menu" className={cn(popoverStyles())}>
            <button
              role="menuitem"
              type="button"
              onClick={handleMenuItemClick}
              className={cn(menuItemStyles())}
            >
              {isPrivate ? 'Make incident public' : 'Convert to private incident'}
            </button>
          </div>
        )}
      </div>

      <ConfirmationDialog
        isOpen={showConfirmation}
        title={dialogTitle}
        message={dialogMessage}
        confirmLabel={confirmLabel}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </>
  );
}
