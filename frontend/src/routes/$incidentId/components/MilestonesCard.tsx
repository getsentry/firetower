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
    timeZoneName: 'short',
  });
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function isMidnight(date: Date): boolean {
  return date.getHours() === 0 && date.getMinutes() === 0;
}

function toMidnight(date: Date): Date {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  return result;
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
    // Build draft values, pre-filling unset fields with default date at midnight
    const drafts: DraftValues = {
      time_started: undefined,
      time_detected: undefined,
      time_analyzed: undefined,
      time_mitigated: undefined,
      time_recovered: undefined,
    };

    for (let i = 0; i < MILESTONES.length; i++) {
      const {field} = MILESTONES[i];
      if (incident[field]) {
        // Field has a real value
        drafts[field] = new Date(incident[field]);
      } else {
        // Pre-fill with default date at midnight
        let defaultDate = new Date(incident.created_at);
        for (let j = i - 1; j >= 0; j--) {
          const prevField = MILESTONES[j].field;
          if (drafts[prevField]) {
            defaultDate = drafts[prevField];
            break;
          }
        }
        drafts[field] = toMidnight(defaultDate);
      }
    }

    setDraftValues(drafts);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      for (let i = 0; i < MILESTONES.length; i++) {
        const {field} = MILESTONES[i];
        const draftValue = draftValues[field];
        const oldValue = incident[field] ? new Date(incident[field]) : undefined;

        // Compute effective value: if it's default date + midnight, treat as unset
        let effectiveValue: Date | undefined = draftValue;
        if (draftValue && isMidnight(draftValue)) {
          const defaultDate = getDefaultDate(i);
          if (isSameDay(draftValue, defaultDate)) {
            effectiveValue = undefined;
          }
        }

        if (effectiveValue?.getTime() !== oldValue?.getTime()) {
          await updateIncidentField.mutateAsync({
            incidentId: incident.id,
            field,
            value: effectiveValue ? effectiveValue.toISOString() : null,
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

  const getDefaultDate = (fieldIndex: number): Date => {
    // Look for the most recent previous milestone that has a value
    for (let i = fieldIndex - 1; i >= 0; i--) {
      const prevField = MILESTONES[i].field;
      if (draftValues[prevField]) {
        return draftValues[prevField];
      }
    }
    // Fall back to incident created_at
    return new Date(incident.created_at);
  };

  const isPlaceholderTime = (fieldIndex: number): boolean => {
    const draftValue = draftValues[MILESTONES[fieldIndex].field];
    if (!draftValue || !isMidnight(draftValue)) return false;
    const defaultDate = getDefaultDate(fieldIndex);
    return isSameDay(draftValue, defaultDate);
  };

  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <h2 className="text-content-headings text-lg font-semibold">Milestones</h2>
        {!isEditing && (
          <Button variant="icon" onClick={startEditing} aria-label="Edit milestones">
            <Pencil className="h-4 w-4" />
          </Button>
        )}
      </div>
      <div className="flex flex-col gap-space-md">
        {MILESTONES.map(({field, label}, index) => (
          <div key={field} className="flex items-center gap-space-md">
            <div className="text-content-secondary w-20 flex-none text-sm font-medium">
              {label}
            </div>
            <div className="flex flex-1 items-center justify-end">
              {isEditing ? (
                <DateTimePicker
                  value={draftValues[field]}
                  onChange={updateDraft(field)}
                  defaultDate={getDefaultDate(index)}
                  isPlaceholderTime={isPlaceholderTime(index)}
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
      {isEditing && (
        <div className="mt-space-lg flex items-center justify-end gap-space-xs">
          <Button variant="primary" onClick={handleSave} loading={isSaving}>
            Save
          </Button>
          <Button variant="secondary" onClick={cancelEditing} disabled={isSaving}>
            Cancel
          </Button>
        </div>
      )}
    </Card>
  );
}
