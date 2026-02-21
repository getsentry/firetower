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

interface DraftValue {
  date: Date | undefined;
  time: string | undefined; // "HH:MM" format
}

type DraftValues = Record<MilestoneField, DraftValue>;

function parseIncidentDateTime(isoString: string | null): DraftValue {
  if (!isoString) return {date: undefined, time: undefined};
  const d = new Date(isoString);
  return {
    date: d,
    time: `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`,
  };
}

function combineDateAndTime(date: Date, time: string): Date {
  const [hours, minutes] = time.split(':').map(Number);
  const result = new Date(date);
  result.setHours(hours, minutes, 0, 0);
  return result;
}

export function MilestonesCard({incident}: MilestonesCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftDowntime, setDraftDowntime] = useState<string>(
    incident.total_downtime != null ? String(incident.total_downtime) : ''
  );
  const [draftValues, setDraftValues] = useState<DraftValues>(() => ({
    time_started: parseIncidentDateTime(incident.time_started),
    time_detected: parseIncidentDateTime(incident.time_detected),
    time_analyzed: parseIncidentDateTime(incident.time_analyzed),
    time_mitigated: parseIncidentDateTime(incident.time_mitigated),
    time_recovered: parseIncidentDateTime(incident.time_recovered),
  }));
  const [isSaving, setIsSaving] = useState(false);

  const queryClient = useQueryClient();
  const updateIncidentField = useMutation(
    updateIncidentFieldMutationOptions(queryClient)
  );

  // For the calendar's default month: use the nearest previous milestone's date,
  // or fall back to incident created_at. This will probably be the correct date and if so, saves the user from inputting date, if not, it's same effort to select date as if it were unset.
  const getDefaultDate = (fieldIndex: number): Date => {
    for (let i = fieldIndex - 1; i >= 0; i--) {
      const prevField = MILESTONES[i].field;
      if (draftValues[prevField].date) {
        return draftValues[prevField].date;
      }
    }
    return new Date(incident.created_at);
  };

  const startEditing = () => {
    setDraftDowntime(
      incident.total_downtime != null ? String(incident.total_downtime) : ''
    );
    const drafts: DraftValues = {
      time_started: parseIncidentDateTime(incident.time_started),
      time_detected: parseIncidentDateTime(incident.time_detected),
      time_analyzed: parseIncidentDateTime(incident.time_analyzed),
      time_mitigated: parseIncidentDateTime(incident.time_mitigated),
      time_recovered: parseIncidentDateTime(incident.time_recovered),
    };

    // Pre-fill dates for unset fields
    for (let i = 0; i < MILESTONES.length; i++) {
      const {field} = MILESTONES[i];
      if (!drafts[field].date) {
        let defaultDate = new Date(incident.created_at);
        for (let j = i - 1; j >= 0; j--) {
          if (drafts[MILESTONES[j].field].date) {
            defaultDate = drafts[MILESTONES[j].field].date!;
            break;
          }
        }
        drafts[field] = {date: defaultDate, time: undefined};
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
      for (const {field} of MILESTONES) {
        const {date, time} = draftValues[field];
        const oldValue = incident[field] ? new Date(incident[field]) : undefined;

        // Only save if both date and time are set
        const effectiveValue = date && time ? combineDateAndTime(date, time) : undefined;

        if (effectiveValue?.getTime() !== oldValue?.getTime()) {
          await updateIncidentField.mutateAsync({
            incidentId: incident.id,
            field,
            value: effectiveValue ? effectiveValue.toISOString() : null,
          });
        }
      }
      const newDowntime =
        draftDowntime.trim() === '' ? null : parseInt(draftDowntime, 10);
      if (newDowntime !== incident.total_downtime) {
        await updateIncidentField.mutateAsync({
          incidentId: incident.id,
          field: 'total_downtime',
          value: newDowntime,
        });
      }

      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  };

  const updateDraftDate = (field: MilestoneField) => (date: Date | undefined) => {
    setDraftValues(prev => ({...prev, [field]: {...prev[field], date}}));
  };

  const updateDraftTime = (field: MilestoneField) => (time: string | undefined) => {
    setDraftValues(prev => ({...prev, [field]: {...prev[field], time}}));
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
                  date={draftValues[field].date}
                  time={draftValues[field].time}
                  onDateChange={updateDraftDate(field)}
                  onTimeChange={updateDraftTime(field)}
                  defaultDate={getDefaultDate(index)}
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
        <div className="flex items-center gap-space-md">
          <div className="text-content-secondary w-20 flex-none text-sm font-medium">
            Downtime
          </div>
          <div className="flex flex-1 items-center justify-end">
            {isEditing ? (
              <div className="flex items-center gap-space-xs">
                <input
                  type="number"
                  min="0"
                  value={draftDowntime}
                  onChange={e => setDraftDowntime(e.target.value)}
                  placeholder="—"
                  className="w-20 rounded-radius-sm border border-secondary bg-background-primary px-space-sm py-space-xs text-right text-sm focus:outline-none focus:ring-1"
                />
                <span className="text-content-secondary text-sm">min</span>
              </div>
            ) : (
              <span
                className={`text-sm ${incident.total_downtime != null ? 'text-content-primary' : 'text-content-tertiary'}`}
              >
                {incident.total_downtime != null
                  ? `${incident.total_downtime} min`
                  : 'Not set'}
              </span>
            )}
          </div>
        </div>
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
