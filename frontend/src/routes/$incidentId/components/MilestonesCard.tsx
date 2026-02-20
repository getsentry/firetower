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

function formatDowntime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours && minutes) return `${hours}h ${minutes}m`;
  if (hours) return `${hours}h`;
  if (minutes) return `${minutes}m`;
  return `${seconds}s`;
}

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
    incident.total_downtime != null ? String(Math.round(incident.total_downtime / 60)) : ''
  );
  const [downtimeError, setDowntimeError] = useState<string | null>(null);
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
    setDraftDowntime(incident.total_downtime != null ? String(Math.round(incident.total_downtime / 60)) : '');
    setDowntimeError(null);
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
    setDowntimeError(null);
  };

  const handleSave = async () => {
    const trimmed = draftDowntime.trim();
    if (trimmed !== '' && (!/^\d+$/.test(trimmed) || Number(trimmed) < 0)) {
      setDowntimeError('Enter a whole number of seconds (e.g. 300 for 5 minutes)');
      return;
    }
    setDowntimeError(null);
    setIsSaving(true);
    try {
      const newDowntime = trimmed === '' ? null : parseInt(trimmed, 10) * 60;
      if (newDowntime !== incident.total_downtime) {
        await updateIncidentField.mutateAsync({
          incidentId: incident.id,
          field: 'total_downtime',
          value: newDowntime,
        });
      }
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
        <h2 className="text-content-headings text-lg font-semibold">Critical Times</h2>
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
              <div className="flex flex-col items-end gap-space-xs">
                <div className="flex items-center gap-space-xs">
                  <input
                    type="text"
                    inputMode="numeric"
                    value={draftDowntime}
                    onChange={e => {
                      setDraftDowntime(e.target.value);
                      setDowntimeError(null);
                    }}
                    placeholder="minutes"
                    className="w-28 rounded-radius-sm border border-border-primary bg-background-primary px-space-sm py-space-xs text-right text-sm text-content-primary focus:border-content-accent focus:outline-none"
                  />
                  <span className="text-content-secondary text-xs">min</span>
                </div>
                {downtimeError && (
                  <span className="text-xs text-content-danger">{downtimeError}</span>
                )}
              </div>
            ) : (
              <span className={`text-sm ${incident.total_downtime != null ? 'text-content-primary' : 'text-content-tertiary'}`}>
                {incident.total_downtime != null
                  ? formatDowntime(incident.total_downtime)
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
