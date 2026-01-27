import {useCallback, useState} from 'react';
import {cva} from 'class-variance-authority';
import {Button} from 'components/Button';
import {ConfirmationDialog} from 'components/ConfirmationDialog';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {EllipsisVertical} from 'lucide-react';
import {cn} from 'utils/cn';

const menuItemStyles = cva([
  'w-full',
  'cursor-pointer',
  'rounded-radius-md',
  'px-space-md',
  'py-space-sm',
  'text-left',
  'text-sm',
  'transition-colors',
  'text-content-primary',
  'bg-background-primary',
  'hover:bg-background-tertiary',
  'select-none',
]);

interface OverflowMenuProps {
  isPrivate: boolean;
  onToggleVisibility: () => Promise<void>;
}

export function OverflowMenu({isPrivate, onToggleVisibility}: OverflowMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const handleMenuItemClick = useCallback(() => {
    setIsOpen(false);
    setShowConfirmation(true);
  }, []);

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

  const dialogTitle = isPrivate
    ? 'Make incident public?'
    : 'Convert to private incident?';
  const dialogMessage = isPrivate
    ? 'This incident will be visible to all users.'
    : 'This incident will only be visible to participants and admins.';
  const confirmLabel = isPrivate ? 'Make public' : 'Convert to private';

  return (
    <>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="icon" disabled={isLoading} aria-label="More actions">
            <EllipsisVertical className="h-5 w-5" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="p-space-sm">
          <button
            role="menuitem"
            type="button"
            onClick={handleMenuItemClick}
            className={cn(menuItemStyles())}
          >
            {isPrivate ? 'Make incident public' : 'Convert to private incident'}
          </button>
        </PopoverContent>
      </Popover>

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
