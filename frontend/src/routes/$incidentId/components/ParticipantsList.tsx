import {useState} from 'react';
import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

const MAX_VISIBLE_PARTICIPANTS = 5;

interface ParticipantsListProps {
  participants: IncidentDetail['participants'];
}

export function ParticipantsList({participants}: ParticipantsListProps) {
  const [expanded, setExpanded] = useState(false);

  if (participants.length === 0) {
    return null;
  }

  const hasMore = participants.length > MAX_VISIBLE_PARTICIPANTS;
  const visibleParticipants = expanded
    ? participants
    : participants.slice(0, MAX_VISIBLE_PARTICIPANTS);
  const hiddenCount = participants.length - MAX_VISIBLE_PARTICIPANTS;

  return (
    <Card>
      <Card.Title>Participants</Card.Title>
      <div className="gap-space-xl grid grid-cols-1">
        {visibleParticipants.map((participant, index) => (
          <div key={index} className="gap-space-lg flex items-center">
            <Avatar name={participant.name} src={participant.avatar_url} />
            <div className="text-content-headings flex-1 font-medium">
              <span className="mt-[2px] block">{participant.name}</span>
            </div>
            {participant.role && participant.role !== 'Participant' && (
              <div className="text-content-secondary text-sm uppercase">
                <span className="mt-[2px] block">{participant.role}</span>
              </div>
            )}
          </div>
        ))}
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
