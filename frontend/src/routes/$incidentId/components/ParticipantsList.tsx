import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {cva} from 'class-variance-authority';
import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';
import {ChevronDown, Pencil, X} from 'lucide-react';
import {cn} from 'utils/cn';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

const MAX_VISIBLE_PARTICIPANTS = 5;

type Participant = IncidentDetail['participants'][number];
type EditableRole = 'Captain' | 'Reporter';

const triggerStyles = cva([
  'inline-flex',
  'items-center',
  'justify-center',
  'transition-all',
  'p-space-xs',
  'rounded-radius-sm',
  'hover:bg-background-secondary',
  'hover:scale-110',
  'focus:outline-auto',
  'text-content-secondary',
  'hover:text-content-primary',
  'cursor-pointer',
]);

const dropdownTriggerStyles = cva([
  'gap-space-sm',
  'px-space-md',
  'py-space-xs',
  'rounded-radius-md',
  'border',
  'border-gray-200',
  'bg-background-primary',
  'text-content-primary',
  'text-sm',
  'cursor-pointer',
  'inline-flex',
  'items-center',
  'focus:outline-auto',
  'focus:border-content-accent',
]);

const dropdownMenuStyles = cva([
  'absolute',
  'z-50',
  'mt-space-xs',
  'rounded-radius-md',
  'border',
  'border-gray-200',
  'bg-background-primary',
  'shadow-lg',
  'p-space-sm',
  'max-h-[200px]',
  'overflow-y-auto',
  '[&::-webkit-scrollbar]:hidden',
  '[-ms-overflow-style:none]',
  '[scrollbar-width:none]',
]);

const dropdownItemStyles = cva(
  [
    'w-full',
    'gap-space-sm',
    'px-space-md',
    'py-space-sm',
    'cursor-pointer',
    'flex',
    'items-center',
    'rounded-radius-sm',
    'text-sm',
  ],
  {
    variants: {
      focused: {
        true: ['bg-background-secondary'],
        false: ['hover:bg-background-tertiary'],
      },
      selected: {
        true: ['font-medium'],
        false: [],
      },
    },
  }
);

interface ParticipantDropdownProps {
  participants: Participant[];
  value: string;
  onChange: (value: string) => void;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

function ParticipantDropdown({
  participants,
  value,
  onChange,
  containerRef,
}: ParticipantDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const selectedParticipant = participants.find(p => p.email === value);
  const currentIndex = participants.findIndex(p => p.email === value);

  const open = useCallback(() => {
    setIsOpen(true);
    setFocusedIndex(currentIndex >= 0 ? currentIndex : 0);
  }, [currentIndex]);

  const close = useCallback((refocus = false) => {
    setIsOpen(false);
    setFocusedIndex(-1);
    if (refocus) {
      triggerRef.current?.focus();
    }
  }, []);

  const handleSelect = useCallback(
    (participant: Participant) => {
      onChange(participant.email);
      close();
    },
    [onChange, close]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!isOpen) {
        if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
          event.preventDefault();
          open();
        }
        return;
      }

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex(prev => (prev + 1) % participants.length);
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex(prev => (prev - 1 + participants.length) % participants.length);
          break;
        case 'Enter':
        case ' ':
          event.preventDefault();
          if (focusedIndex >= 0) {
            handleSelect(participants[focusedIndex]);
          }
          break;
        case 'Escape':
          event.preventDefault();
          close(true);
          break;
        case 'Tab':
          close();
          break;
      }
    },
    [isOpen, open, close, focusedIndex, participants, handleSelect]
  );

  const handleBlur = useCallback(
    (e: React.FocusEvent) => {
      // Close if focus moves outside the dropdown container
      if (!e.currentTarget.contains(e.relatedTarget)) {
        close();
      }
    },
    [close]
  );

  // Focus trigger on mount
  useEffect(() => {
    triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (isOpen && focusedIndex >= 0 && menuRef.current) {
      const items = menuRef.current.querySelectorAll('[role="option"]');
      const focusedElement = items[focusedIndex] as HTMLElement;
      focusedElement?.scrollIntoView({block: 'nearest'});
    }
  }, [isOpen, focusedIndex]);

  useEffect(() => {
    if (isOpen && containerRef?.current && triggerRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const triggerRect = triggerRef.current.getBoundingClientRect();
      setMenuStyle({
        left: containerRect.left - triggerRect.left,
        width: containerRect.width,
      });
    }
  }, [isOpen, containerRef]);

  return (
    <div className="relative w-full" onBlur={handleBlur}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (isOpen ? close() : open())}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={cn(dropdownTriggerStyles(), 'w-full')}
      >
        {selectedParticipant && (
          <Avatar
            name={selectedParticipant.name}
            src={selectedParticipant.avatar_url}
            size="sm"
          />
        )}
        <span className="min-w-0 flex-1 truncate text-left">
          {selectedParticipant?.name ?? value}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0" />
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          role="listbox"
          className={cn(dropdownMenuStyles())}
          style={menuStyle}
        >
          {participants.map((participant, index) => (
            <div
              key={participant.email}
              role="option"
              tabIndex={-1}
              aria-selected={participant.email === value}
              className={cn(
                dropdownItemStyles({
                  focused: index === focusedIndex,
                  selected: participant.email === value,
                })
              )}
              onClick={() => handleSelect(participant)}
              onMouseEnter={() => setFocusedIndex(index)}
            >
              <Avatar name={participant.name} src={participant.avatar_url} size="sm" />
              <span>{participant.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ParticipantsListProps {
  incidentId: string;
  participants: IncidentDetail['participants'];
}

export function ParticipantsList({incidentId, participants}: ParticipantsListProps) {
  const queryClient = useQueryClient();
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [editingRole, setEditingRole] = useState<EditableRole | null>(null);
  const [selectedParticipantEmail, setSelectedParticipantEmail] = useState<string>('');

  // Memoize sorted participants list for display (may have duplicates if captain === reporter)
  const displayParticipants = useMemo(() => {
    const sorted = [...participants].sort((a, b) => a.name.localeCompare(b.name));
    const captain = sorted.find(p => p.role === 'Captain');
    const reporter = sorted.find(p => p.role === 'Reporter');
    const others = sorted.filter(p => p.role !== 'Captain' && p.role !== 'Reporter');
    return [captain, reporter, ...others].filter(Boolean) as Participant[];
  }, [participants]);

  // Deduplicated list for dropdown selection
  const dropdownParticipants = useMemo(() => {
    const seen = new Set<string>();
    return displayParticipants.filter(p => {
      if (seen.has(p.email)) return false;
      seen.add(p.email);
      return true;
    });
  }, [displayParticipants]);

  if (participants.length === 0) {
    return null;
  }

  const hasMore = displayParticipants.length > MAX_VISIBLE_PARTICIPANTS;
  const visibleParticipants = expanded
    ? displayParticipants
    : displayParticipants.slice(0, MAX_VISIBLE_PARTICIPANTS);
  const hiddenCount = displayParticipants.length - MAX_VISIBLE_PARTICIPANTS;

  const getParticipantRole = (participant: Participant): EditableRole | null =>
    participant.role === 'Participant' ? null : participant.role;

  const startEditing = (role: EditableRole, currentHolderEmail: string) => {
    setEditingRole(role);
    setSelectedParticipantEmail(currentHolderEmail);
  };

  const cancelEditing = () => {
    setEditingRole(null);
    setSelectedParticipantEmail('');
  };

  const handleRoleChange = async (email: string) => {
    if (!editingRole) return;

    const field = editingRole.toLowerCase() as 'captain' | 'reporter';
    try {
      await updateIncidentField.mutateAsync({
        incidentId,
        field,
        value: email,
      });
    } catch (err) {
      console.error('Failed to save:', err);
    } finally {
      setEditingRole(null);
      setSelectedParticipantEmail('');
    }
  };

  const renderRoleDisplay = (participant: Participant, role: string) => {
    const isEditable = role === 'Captain' || role === 'Reporter';
    const isEditingThis = editingRole === role;

    if (isEditingThis) {
      return (
        <div className="gap-space-sm flex flex-1 items-center">
          <div className="flex-1">
            <ParticipantDropdown
              participants={dropdownParticipants}
              value={selectedParticipantEmail}
              onChange={handleRoleChange}
              containerRef={containerRef}
            />
          </div>
          <div className="gap-space-xs flex items-center">
            <div className="text-content-secondary text-sm uppercase">{role}</div>
            <button
              type="button"
              onClick={cancelEditing}
              aria-label="Cancel"
              className={cn(triggerStyles())}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="gap-space-xs flex items-center">
        <div className="text-content-secondary text-sm uppercase">{role}</div>
        {isEditable && (
          <button
            type="button"
            onClick={() => startEditing(role as EditableRole, participant.email)}
            aria-label={`Edit ${role}`}
            className={cn(triggerStyles())}
          >
            <Pencil className="h-4 w-4" />
          </button>
        )}
      </div>
    );
  };

  return (
    <Card>
      <Card.Title>Participants</Card.Title>
      <div ref={containerRef} className="gap-space-xl grid grid-cols-1">
        {visibleParticipants.map((participant, index) => {
          const role = getParticipantRole(participant);
          const isEditingThisRow = editingRole !== null && role === editingRole;
          return (
            <div key={index} className="gap-space-lg flex items-center">
              {!isEditingThisRow && (
                <>
                  <Avatar name={participant.name} src={participant.avatar_url} />
                  <div className="text-content-headings flex-1 font-medium">
                    {participant.name}
                  </div>
                </>
              )}
              {role && renderRoleDisplay(participant, role)}
            </div>
          );
        })}
        {hasMore && (
          <div className="text-center">
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-content-secondary hover:text-content-accent px-space-md py-space-xs cursor-pointer text-xs"
            >
              {expanded
                ? 'Show fewer participants'
                : `Show ${hiddenCount} more participants`}
            </button>
          </div>
        )}
      </div>
    </Card>
  );
}
