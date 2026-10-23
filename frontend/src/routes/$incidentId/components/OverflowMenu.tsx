import {useCallback, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {buttonStyles} from 'components/buttonStyles';
import {ConfirmationDialog} from 'components/ConfirmationDialog';
import {Popover, PopoverContent, PopoverTrigger} from 'components/Popover';
import {EllipsisVertical} from 'lucide-react';

import {background, content, radius, space} from '../../../styles/tokens.stylex';

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
          <button
            type="button"
            {...stylex.props(buttonStyles({variant: 'icon'}))}
            disabled={isLoading}
            aria-label="More actions"
          >
            <EllipsisVertical {...stylex.props(styles.icon)} />
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" style={styles.content}>
          <button
            role="menuitem"
            type="button"
            onClick={handleMenuItemClick}
            {...stylex.props(styles.menuItem)}
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

const styles = stylex.create({
  icon: {height: '20px', width: '20px'},
  content: {padding: space.sm},
  menuItem: {
    width: '100%',
    cursor: 'pointer',
    borderRadius: radius.md,
    paddingLeft: space.md,
    paddingRight: space.md,
    paddingTop: space.sm,
    paddingBottom: space.sm,
    textAlign: 'left',
    fontSize: 14,
    lineHeight: '20px',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionDuration: '150ms',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    color: content.primary,
    backgroundColor: {default: background.primary, ':hover': background.tertiary},
    userSelect: 'none',
  },
});
