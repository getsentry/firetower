interface DowntimeFieldProps {
  isEditing: boolean;
  value: number | null;
  draftValue: number | null;
  onChange: (value: number | null) => void;
}

export function DowntimeField({
  isEditing,
  value,
  draftValue,
  onChange,
}: DowntimeFieldProps) {
  return (
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
              value={draftValue ?? ''}
              onChange={e =>
                onChange(e.target.value === '' ? null : e.target.valueAsNumber)
              }
              placeholder="—"
              className="w-20 rounded-radius-sm border border-secondary bg-background-primary px-space-sm py-space-xs text-right text-sm focus:outline-none focus:ring-1"
            />
            <span className="text-content-secondary text-sm">min</span>
          </div>
        ) : (
          <span
            className={`text-sm ${value != null ? 'text-content-primary' : 'text-content-tertiary'}`}
          >
            {value != null ? `${value} min` : 'Not set'}
          </span>
        )}
      </div>
    </div>
  );
}
