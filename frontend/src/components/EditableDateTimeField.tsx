import {useCallback, useState} from 'react';
import {Check, Pencil} from 'lucide-react';

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
    <div className="flex items-center gap-space-md">
      <div className="text-content-secondary w-20 flex-none text-sm font-medium">
        {label}
      </div>

      <div className="flex flex-1 items-center justify-end">
        {isEditing ? (
          <div className="flex shrink-0 items-center gap-space-sm">
            <DateTimePicker
              date={draftDate}
              time={draftTime}
              onDateChange={setDraftDate}
              onTimeChange={setDraftTime}
            />
            <Button variant="icon" onClick={save} disabled={isSaving} aria-label="Save">
              <Check className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-space-xs">
            <span
              className={`text-sm ${value ? 'text-content-primary' : 'text-content-tertiary italic'}`}
            >
              {formatDateTime(value) || placeholder}
            </span>
            <Button variant="icon" onClick={startEditing} aria-label={`Edit ${label}`}>
              <Pencil className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
