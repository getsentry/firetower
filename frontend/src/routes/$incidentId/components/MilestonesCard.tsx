import {useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useMutation, useQueryClient} from '@tanstack/react-query';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {DateTimePicker} from 'components/DateTimePicker';
import {Pencil} from 'lucide-react';

import {content, fontWeight, space} from '../../../styles/tokens.stylex';
import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';
import {updateIncidentFieldMutationOptions} from '../queries/updateIncidentFieldMutationOptions';

import {DowntimeField} from './DowntimeField';

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
  time: string | undefined;
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
  const [draftDowntime, setDraftDowntime] = useState<number | null>(
    incident.total_downtime
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

  const getPreviousMilestoneDateOrCreatedAt = (fieldIndex: number): Date => {
    for (let i = fieldIndex - 1; i >= 0; i--) {
      const prevField = MILESTONES[i].field;
      if (draftValues[prevField].date) {
        return draftValues[prevField].date;
      }
    }
    return new Date(incident.created_at);
  };

  const startEditing = () => {
    setDraftDowntime(incident.total_downtime);
    const drafts: DraftValues = {
      time_started: parseIncidentDateTime(incident.time_started),
      time_detected: parseIncidentDateTime(incident.time_detected),
      time_analyzed: parseIncidentDateTime(incident.time_analyzed),
      time_mitigated: parseIncidentDateTime(incident.time_mitigated),
      time_recovered: parseIncidentDateTime(incident.time_recovered),
    };

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

        const effectiveValue = date && time ? combineDateAndTime(date, time) : undefined;

        if (effectiveValue?.getTime() !== oldValue?.getTime()) {
          await updateIncidentField.mutateAsync({
            incidentId: incident.id,
            field,
            value: effectiveValue ? effectiveValue.toISOString() : null,
          });
        }
      }
      if (draftDowntime !== incident.total_downtime) {
        await updateIncidentField.mutateAsync({
          incidentId: incident.id,
          field: 'total_downtime',
          value: draftDowntime,
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
      <div {...stylex.props(styles.header)}>
        <h2 {...stylex.props(styles.heading)}>Milestones</h2>
        {!isEditing && (
          <Button variant="icon" onClick={startEditing} aria-label="Edit milestones">
            <Pencil {...stylex.props(styles.icon)} />
          </Button>
        )}
      </div>
      <div {...stylex.props(styles.milestones)}>
        {MILESTONES.map(({field, label}, index) => (
          <div key={field} {...stylex.props(styles.row)}>
            <div {...stylex.props(styles.label)}>{label}</div>
            <div {...stylex.props(styles.value)}>
              {isEditing ? (
                <DateTimePicker
                  date={draftValues[field].date}
                  time={draftValues[field].time}
                  onDateChange={updateDraftDate(field)}
                  onTimeChange={updateDraftTime(field)}
                  defaultDate={getPreviousMilestoneDateOrCreatedAt(index)}
                />
              ) : (
                <span
                  {...stylex.props(
                    styles.displayValue,
                    incident[field] ? styles.presentValue : styles.emptyValue
                  )}
                >
                  {formatDateTime(
                    incident[field] ? new Date(incident[field]) : undefined
                  ) || 'Not set'}
                </span>
              )}
            </div>
          </div>
        ))}
        <DowntimeField
          isEditing={isEditing}
          value={incident.total_downtime}
          draftValue={draftDowntime}
          onChange={setDraftDowntime}
        />
      </div>
      {isEditing && (
        <div {...stylex.props(styles.actions)}>
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

const styles = stylex.create({
  header: {
    marginBottom: space.lg,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heading: {
    color: content.headings,
    fontSize: '18px',
    lineHeight: '28px',
    fontWeight: 600,
  },
  icon: {height: '16px', width: '16px'},
  milestones: {gap: space.md, display: 'flex', flexDirection: 'column'},
  row: {gap: space.md, display: 'flex', alignItems: 'center'},
  label: {
    color: content.secondary,
    width: '80px',
    flex: 'none',
    fontSize: '14px',
    lineHeight: '20px',
    fontWeight: fontWeight.medium,
  },
  value: {
    display: 'flex',
    flex: '1 1 0%',
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  actions: {
    marginTop: space.lg,
    gap: space.xs,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  displayValue: {fontSize: 14, lineHeight: '20px'},
  presentValue: {color: content.primary},
  emptyValue: {color: content.secondary},
});
