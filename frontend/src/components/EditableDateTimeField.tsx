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

export function EditableDateTimeField({
  value,
  onSave,
  label,
  placeholder = 'Not set',
}: EditableDateTimeFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState<Date | undefined>(value);
  const [isSaving, setIsSaving] = useState(false);

  const startEditing = useCallback(() => {
    setIsEditing(true);
    setDraftValue(value);
  }, [value]);

  const save = useCallback(async () => {
    if (draftValue?.getTime() === value?.getTime()) {
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      await onSave(draftValue);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }, [draftValue, value, onSave]);

  return (
    <div className="flex items-center gap-space-md">
      <div className="text-content-secondary w-20 flex-none text-sm font-medium">
        {label}
      </div>

      <div className="flex flex-1 items-center justify-end">
        {isEditing ? (
          <div className="flex shrink-0 items-center gap-space-sm">
            <DateTimePicker value={draftValue} onChange={setDraftValue} />
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
