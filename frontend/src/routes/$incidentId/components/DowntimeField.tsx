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
    <div className="gap-space-md flex items-center">
      <div className="text-content-secondary w-20 flex-none text-sm font-medium">
        Downtime
      </div>
      <div className="flex flex-1 items-center justify-end">
        {isEditing ? (
          <div className="gap-space-xs flex items-center">
            <input
              type="number"
              min="0"
              value={draftValue ?? ''}
              onChange={e => {
                const num = e.target.valueAsNumber;
                onChange(e.target.value === '' ? null : Number.isNaN(num) ? null : num);
              }}
              placeholder="—"
              className="rounded-radius-sm border-secondary bg-background-primary px-space-sm py-space-xs w-20 border text-right text-sm focus:ring-1 focus:outline-none"
            />
            <span className="text-content-secondary text-sm">min</span>
          </div>
        ) : (
          <span
            className={`text-sm ${value != null ? 'text-content-primary' : 'text-content-secondary'}`}
          >
            {value != null ? `${value} min` : 'Not set'}
          </span>
        )}
      </div>
    </div>
  );
}
