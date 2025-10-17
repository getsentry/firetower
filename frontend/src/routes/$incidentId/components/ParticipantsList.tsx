import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

interface ParticipantsListProps {
  participants: IncidentDetail['participants'];
}

export function ParticipantsList({participants}: ParticipantsListProps) {
  if (participants.length === 0) {
    return null;
  }

  return (
    <Card>
      <Card.Title>Participants</Card.Title>
      <div className="gap-space-xl grid grid-cols-1">
        {participants.map((participant, index) => (
          <div key={index} className="gap-space-lg flex items-center">
            <Avatar name={participant.name} src={participant.avatar_url} size="lg" />
            <div className="flex flex-1 flex-col justify-center">
              <div className="flex items-center justify-between">
                <div className="text-content-headings font-medium">
                  {participant.name}
                </div>
                {participant.role && (
                  <div className="text-content-secondary text-sm uppercase">
                    {participant.role}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
