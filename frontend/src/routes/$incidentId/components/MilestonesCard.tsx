import {Card} from 'components/Card';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

interface MilestonesCardProps {
  incident: IncidentDetail;
}

type MilestoneField =
  | 'time_started'
  | 'time_detected'
  | 'time_analyzed'
  | 'time_mitigated'
  | 'time_recovered';

interface MilestoneConfig {
  field: MilestoneField;
  label: string;
}

const MILESTONES: MilestoneConfig[] = [
  {field: 'time_started', label: 'Started'},
  {field: 'time_detected', label: 'Detected'},
  {field: 'time_analyzed', label: 'Analyzed'},
  {field: 'time_mitigated', label: 'Mitigated'},
  {field: 'time_recovered', label: 'Recovered'},
];

function formatDateTime(dateString: string | null): string {
  if (!dateString) return 'Not set';

  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

export function MilestonesCard({incident}: MilestonesCardProps) {
  return (
    <Card>
      <h2 className="text-content-headings mb-space-lg text-lg font-semibold">
        Timeline
      </h2>
      <div className="grid grid-cols-2 gap-space-lg md:grid-cols-5">
        {MILESTONES.map(({field, label}) => (
          <div key={field} className="flex flex-col">
            <div className="text-content-secondary mb-space-xs text-sm font-medium">
              {label}
            </div>
            <span
              className={
                incident[field] ? 'text-content-primary' : 'text-content-tertiary italic'
              }
            >
              {formatDateTime(incident[field])}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
