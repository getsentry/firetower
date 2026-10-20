import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {Avatar} from 'components/Avatar';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {Pencil, X} from 'lucide-react';

import {
  background,
  content,
  fontWeight,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import {currentUserQueryOptions} from '../../queries/currentUserQueryOptions';
import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

const MAX_VISIBLE_PARTICIPANTS = 5;

type Participant = IncidentDetail['participants'][number];
type EditableRole = 'Captain' | 'Reporter';

interface ParticipantDropdownProps {
  participants: Participant[];
  value: string;
  onChange: (value: string) => void;
  containerRef?: React.RefObject<HTMLDivElement | null>;
  currentUserEmail?: string;
}

function ParticipantDropdown({
  participants,
  value,
  onChange,
  containerRef,
  currentUserEmail,
}: ParticipantDropdownProps) {
  const [searchValue, setSearchValue] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [menuMeasurements, setMenuMeasurements] = useState<{
    left: number;
    width: number;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const selectedParticipant = participants.find(p => p.email === value);

  const filteredParticipants = useMemo(() => {
    const filtered = participants.filter(p =>
      p.name.toLowerCase().includes(searchValue.toLowerCase())
    );
    return filtered.sort((a, b) => {
      if (currentUserEmail && a.email === currentUserEmail) return -1;
      if (currentUserEmail && b.email === currentUserEmail) return 1;
      return 0;
    });
  }, [participants, searchValue, currentUserEmail]);

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
      setMenuMeasurements({
        left: containerRect.left - inputRect.left,
        width: containerRect.width,
      });
    }
  }, [containerRef]);

  return (
    <div {...stylex.props(styles.container)}>
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
        {...stylex.props(styles.dropdownTrigger)}
      />

      <div
        ref={menuRef}
        role="listbox"
        {...stylex.props(
          styles.dropdownMenu,
          menuMeasurements &&
            styles.menuPosition(menuMeasurements.left, menuMeasurements.width)
        )}
      >
        {filteredParticipants.length === 0 ? (
          <div {...stylex.props(styles.empty)}>No participants match</div>
        ) : (
          filteredParticipants.map((participant, index) => (
            <div
              key={participant.email}
              role="option"
              aria-selected={participant.email === value}
              {...stylex.props(
                styles.dropdownItem,
                index === focusedIndex ? styles.focusedItem : styles.unfocusedItem,
                participant.email === value && styles.selectedItem
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
  const {data: currentUser} = useQuery(currentUserQueryOptions());
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [editingRole, setEditingRole] = useState<EditableRole | null>(null);
  const [selectedParticipantEmail, setSelectedParticipantEmail] = useState<string>('');

  const displayParticipants = useMemo(() => {
    const sorted = [...participants].sort((a, b) => a.name.localeCompare(b.name));
    const captain = sorted.find(p => p.role === 'Captain');
    const reporter = sorted.find(p => p.role === 'Reporter');
    const others = sorted.filter(p => p.role !== 'Captain' && p.role !== 'Reporter');
    return [captain, reporter, ...others].filter(Boolean) as Participant[];
  }, [participants]);

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
        <div {...stylex.props(styles.editing)}>
          <div {...stylex.props(styles.grow)}>
            <ParticipantDropdown
              participants={dropdownParticipants}
              value={selectedParticipantEmail}
              onChange={handleRoleChange}
              containerRef={containerRef}
              currentUserEmail={currentUser?.email}
            />
          </div>
          <div {...stylex.props(styles.roleContainer)}>
            <div {...stylex.props(styles.role)}>{role}</div>
            <Button variant="icon" onClick={cancelEditing} aria-label="Cancel">
              <X {...stylex.props(styles.icon)} />
            </Button>
          </div>
        </div>
      );
    }

    return (
      <div {...stylex.props(styles.roleContainer)}>
        <div {...stylex.props(styles.role)}>{role}</div>
        {isEditable && (
          <Button
            variant="icon"
            onClick={() => startEditing(role as EditableRole, participant.email)}
            aria-label={`Edit ${role}`}
          >
            <Pencil {...stylex.props(styles.icon)} />
          </Button>
        )}
      </div>
    );
  };

  return (
    <Card>
      <Card.Title>Participants</Card.Title>
      <div ref={containerRef} {...stylex.props(styles.list)}>
        {visibleParticipants.map((participant, index) => {
          const role = getParticipantRole(participant);
          const isEditingThisRow = editingRole !== null && role === editingRole;
          return (
            <div key={index} {...stylex.props(styles.row)}>
              {!isEditingThisRow && (
                <>
                  <Avatar name={participant.name} src={participant.avatar_url} />
                  <div {...stylex.props(styles.name)}>{participant.name}</div>
                </>
              )}
              {role && renderRoleDisplay(participant, role)}
            </div>
          );
        })}
        {hasMore && (
          <div {...stylex.props(styles.moreContainer)}>
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              {...stylex.props(styles.more)}
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

const styles = stylex.create({
  container: {position: 'relative', width: '100%'},
  empty: {
    paddingLeft: space.md,
    paddingRight: space.md,
    paddingTop: space.sm,
    paddingBottom: space.sm,
    color: content.secondary,
    fontSize: '14px',
    lineHeight: '20px',
  },
  editing: {gap: space.sm, display: 'flex', flex: '1 1 0%', alignItems: 'center'},
  grow: {flex: '1 1 0%'},
  roleContainer: {gap: space.xs, display: 'flex', alignItems: 'center'},
  role: {
    color: content.secondary,
    fontSize: '14px',
    lineHeight: '20px',
    textTransform: 'uppercase',
  },
  icon: {height: '16px', width: '16px'},
  list: {
    gap: space.xl,
    display: 'grid',
    gridTemplateColumns: 'repeat(1, minmax(0, 1fr))',
  },
  row: {gap: space.lg, display: 'flex', minHeight: '40px', alignItems: 'center'},
  name: {color: content.headings, flex: '1 1 0%', fontWeight: fontWeight.medium},
  moreContainer: {textAlign: 'center'},
  more: {
    color: {default: content.secondary, ':hover': content.accent},
    paddingLeft: space.md,
    paddingRight: space.md,
    paddingTop: space.xs,
    paddingBottom: space.xs,
    cursor: 'pointer',
    fontSize: '12px',
    lineHeight: '16px',
  },
  dropdownTrigger: {
    gap: space.sm,
    paddingLeft: space.md,
    paddingRight: space.md,
    paddingTop: space.xs,
    paddingBottom: space.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: '#e5e7eb',
    backgroundColor: background.primary,
    color: content.primary,
    fontSize: 14,
    lineHeight: '20px',
    cursor: 'text',
    display: 'inline-flex',
    alignItems: 'center',
    userSelect: 'none',
    width: '100%',
  },
  dropdownMenu: {
    position: 'absolute',
    zIndex: 50,
    marginTop: space.xs,
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: '#e5e7eb',
    backgroundColor: background.primary,
    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    padding: space.sm,
    maxHeight: 200,
    overflowY: 'auto',
    scrollbarWidth: 'none',
    display: {default: null, '::-webkit-scrollbar': 'none'},
  },
  menuPosition: (left: number, width: number) => ({left, width}),
  dropdownItem: {
    width: '100%',
    gap: space.sm,
    paddingLeft: space.md,
    paddingRight: space.md,
    paddingTop: space.sm,
    paddingBottom: space.sm,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    borderRadius: radius.sm,
    fontSize: 14,
    lineHeight: '20px',
    userSelect: 'none',
  },
  focusedItem: {backgroundColor: background.secondary},
  unfocusedItem: {backgroundColor: {default: null, ':hover': background.tertiary}},
  selectedItem: {fontWeight: fontWeight.medium},
});
