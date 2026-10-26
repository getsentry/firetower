import {useCallback, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Check, Pencil} from 'lucide-react';

import {content, fontWeight, space} from '../styles/tokens.stylex';

import {Button} from './Button';
import {DateTimePicker} from './DateTimePicker';

export interface EditableDateTimeFieldProps {
  value: Date | undefined;
  onSave: (date: Date | undefined) => Promise<void>;
  label: string;
  placeholder?: string;
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
  });
}

function parseDateTime(date: Date | undefined): {
  date: Date | undefined;
  time: string | undefined;
} {
  if (!date) return {date: undefined, time: undefined};
  return {
    date,
    time: `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`,
  };
}

function combineDateAndTime(date: Date, time: string): Date {
  const [hours, minutes] = time.split(':').map(Number);
  const result = new Date(date);
  result.setHours(hours, minutes, 0, 0);
  return result;
}

export function EditableDateTimeField({
  value,
  onSave,
  label,
  placeholder = 'Not set',
}: EditableDateTimeFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftDate, setDraftDate] = useState<Date | undefined>(undefined);
  const [draftTime, setDraftTime] = useState<string | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);

  const startEditing = useCallback(() => {
    const parsed = parseDateTime(value);
    setDraftDate(parsed.date);
    setDraftTime(parsed.time);
    setIsEditing(true);
  }, [value]);

  const save = useCallback(async () => {
    const newValue =
      draftDate && draftTime ? combineDateAndTime(draftDate, draftTime) : undefined;

    if (newValue?.getTime() === value?.getTime()) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      await onSave(newValue);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }, [draftDate, draftTime, value, onSave]);

  return (
    <div {...stylex.props(styles.row)}>
      <div {...stylex.props(styles.label)}>{label}</div>

      <div {...stylex.props(styles.valueContainer)}>
        {isEditing ? (
          <div {...stylex.props(styles.editor)}>
            <DateTimePicker
              date={draftDate}
              time={draftTime}
              onDateChange={setDraftDate}
              onTimeChange={setDraftTime}
            />
            <Button variant="icon" onClick={save} disabled={isSaving} aria-label="Save">
              <Check {...stylex.props(styles.icon)} />
            </Button>
          </div>
        ) : (
          <div {...stylex.props(styles.displayRow)}>
            <span
              {...stylex.props(styles.value, value ? styles.present : styles.placeholder)}
            >
              {formatDateTime(value) || placeholder}
            </span>
            <Button variant="icon" onClick={startEditing} aria-label={`Edit ${label}`}>
              <Pencil {...stylex.props(styles.icon)} />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = stylex.create({
  row: {gap: space.md, display: 'flex', alignItems: 'center'},
  label: {
    color: content.secondary,
    width: 80,
    flex: 'none',
    fontSize: 14,
    lineHeight: '20px',
    fontWeight: fontWeight.medium,
  },
  valueContainer: {
    display: 'flex',
    flex: '1',
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
  editor: {gap: space.sm, display: 'flex', flexShrink: 0, alignItems: 'center'},
  icon: {height: 16, width: 16},
  displayRow: {gap: space.xs, display: 'flex', alignItems: 'center'},
  value: {fontSize: 14, lineHeight: '20px'},
  present: {color: content.primary},
  placeholder: {color: content.secondary, fontStyle: 'italic'},
});
