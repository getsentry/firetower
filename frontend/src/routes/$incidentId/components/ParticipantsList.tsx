import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {cva} from 'class-variance-authority';
import {Avatar} from 'components/Avatar';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {Pencil, X} from 'lucide-react';
import {cn} from 'utils/cn';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

const MAX_VISIBLE_PARTICIPANTS = 5;

type Participant = IncidentDetail['participants'][number];
type EditableRole = 'Captain' | 'Reporter';

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
  'select-none',
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
    'select-none',
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
  const [searchValue, setSearchValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const selectedParticipant = participants.find(p => p.email === value);

  const filteredParticipants = useMemo(
    () =>
      participants.filter(p => p.name.toLowerCase().includes(searchValue.toLowerCase())),
    [participants, searchValue]
  );

  const handleSelect = useCallback(
    (participant: Participant) => {
      onChange(participant.email);
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setFocusedIndex(prev =>
            filteredParticipants.length === 0
              ? -1
              : (prev + 1) % filteredParticipants.length
          );
          break;
        case 'ArrowUp':
          event.preventDefault();
          setFocusedIndex(prev =>
            filteredParticipants.length === 0
              ? -1
              : (prev - 1 + filteredParticipants.length) % filteredParticipants.length
          );
          break;
        case 'Enter':
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < filteredParticipants.length) {
            handleSelect(filteredParticipants[focusedIndex]);
          }
          break;
        case 'Escape':
          event.preventDefault();
          inputRef.current?.blur();
          break;
        case 'Tab':
          break;
      }
    },
    [focusedIndex, filteredParticipants, handleSelect]
  );

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (focusedIndex >= 0 && menuRef.current) {
      const items = menuRef.current.querySelectorAll('[role="option"]');
      const focusedElement = items[focusedIndex] as HTMLElement;
      focusedElement?.scrollIntoView({block: 'nearest'});
    }
  }, [focusedIndex]);

  useEffect(() => {
    if (containerRef?.current && inputRef.current) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const inputRect = inputRef.current.getBoundingClientRect();
      setMenuStyle({
        left: containerRect.left - inputRect.left,
        width: containerRect.width,
      });
    }
  }, [containerRef]);

  return (
    <div className="relative w-full">
      <input
        ref={inputRef}
        type="text"
        value={searchValue}
        onChange={e => {
          setSearchValue(e.target.value);
          setFocusedIndex(0);
        }}
        onKeyDown={handleKeyDown}
        placeholder={selectedParticipant?.name ?? value}
        aria-haspopup="listbox"
        aria-expanded={true}
        className={cn(dropdownTriggerStyles(), 'w-full cursor-text')}
      />

      <div
        ref={menuRef}
        role="listbox"
        className={cn(dropdownMenuStyles())}
        style={menuStyle}
      >
        {filteredParticipants.length === 0 ? (
          <div className="px-space-md py-space-sm text-content-secondary text-sm">
            No participants match
          </div>
        ) : (
          filteredParticipants.map((participant, index) => (
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
          ))
        )}
      </div>
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
            <Button variant="icon" onClick={cancelEditing} aria-label="Cancel">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div className="gap-space-xs flex items-center">
        <div className="text-content-secondary text-sm uppercase">{role}</div>
        {isEditable && (
          <Button
            variant="icon"
            onClick={() => startEditing(role as EditableRole, participant.email)}
            aria-label={`Edit ${role}`}
          >
            <Pencil className="h-4 w-4" />
          </Button>
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
            <div key={index} className="gap-space-lg flex min-h-10 items-center">
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
