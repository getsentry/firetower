import {useEffect, useRef, useState} from 'react';
import {EllipsisVertical} from 'lucide-react';

interface OverflowMenuProps {
  isPrivate: boolean;
  onToggleVisibility: () => void;
}

export function OverflowMenu({isPrivate, onToggleVisibility}: OverflowMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="text-content-secondary hover:text-content-primary hover:bg-background-secondary rounded-radius-sm p-space-xs transition-colors"
        aria-label="More actions"
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        <EllipsisVertical className="h-5 w-5" />
      </button>

      {isOpen && (
        <div
          role="menu"
          className="bg-background-primary absolute top-full right-0 z-10 mt-1 min-w-40 rounded-lg border shadow-lg"
        >
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              onToggleVisibility();
              setIsOpen(false);
            }}
            className="hover:bg-background-secondary w-full px-4 py-2 text-left text-sm transition-colors"
          >
            {isPrivate ? 'Make public' : 'Make private'}
          </button>
        </div>
      )}
    </div>
  );
}
