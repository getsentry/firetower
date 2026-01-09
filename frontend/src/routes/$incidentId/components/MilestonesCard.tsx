import {useState} from 'react';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {DateTimePicker} from 'components/DateTimePicker';
import {Pencil} from 'lucide-react';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

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

function formatDateTime(date: Date | undefined): string {
  if (!date) return '';

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

type DraftValues = Record<MilestoneField, Date | undefined>;

export function MilestonesCard({incident}: MilestonesCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftValues, setDraftValues] = useState<DraftValues>(() => ({
    time_started: incident.time_started ? new Date(incident.time_started) : undefined,
    time_detected: incident.time_detected ? new Date(incident.time_detected) : undefined,
    time_analyzed: incident.time_analyzed ? new Date(incident.time_analyzed) : undefined,
    time_mitigated: incident.time_mitigated
      ? new Date(incident.time_mitigated)
      : undefined,
    time_recovered: incident.time_recovered
      ? new Date(incident.time_recovered)
      : undefined,
  }));
  const [isSaving, setIsSaving] = useState(false);

  const queryClient = useQueryClient();
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

  const startEditing = () => {
    setDraftValues({
      time_started: incident.time_started ? new Date(incident.time_started) : undefined,
      time_detected: incident.time_detected
        ? new Date(incident.time_detected)
        : undefined,
      time_analyzed: incident.time_analyzed
        ? new Date(incident.time_analyzed)
        : undefined,
      time_mitigated: incident.time_mitigated
        ? new Date(incident.time_mitigated)
        : undefined,
      time_recovered: incident.time_recovered
        ? new Date(incident.time_recovered)
        : undefined,
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      for (const {field} of MILESTONES) {
        const newValue = draftValues[field];
        const oldValue = incident[field] ? new Date(incident[field]) : undefined;

        if (newValue?.getTime() !== oldValue?.getTime()) {
          await updateIncidentField.mutateAsync({
            incidentId: incident.id,
            field,
            value: newValue ? newValue.toISOString() : null,
          });
        }
      }
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  };

  const updateDraft = (field: MilestoneField) => (date: Date | undefined) => {
    setDraftValues(prev => ({...prev, [field]: date}));
  };

  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <h2 className="text-content-headings text-lg font-semibold">Milestones</h2>
        {isEditing ? (
          <div className="flex items-center gap-space-xs">
            <Button variant="primary" onClick={handleSave} loading={isSaving}>
              Save
            </Button>
            <Button variant="secondary" onClick={cancelEditing} disabled={isSaving}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="icon" onClick={startEditing} aria-label="Edit milestones">
            <Pencil className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-space-md">
        {MILESTONES.map(({field, label}) => (
          <div key={field} className="flex items-center gap-space-md">
            <div className="text-content-secondary w-20 flex-none text-sm font-medium">
              {label}
            </div>
            <div className="flex flex-1 items-center justify-end">
              {isEditing ? (
                <DateTimePicker
                  value={draftValues[field]}
                  onChange={updateDraft(field)}
                />
              ) : (
                <span
                  className={`text-sm ${incident[field] ? 'text-content-primary' : 'text-content-tertiary'}`}
                >
                  {formatDateTime(
                    incident[field] ? new Date(incident[field]) : undefined
                  ) || 'Not set'}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
