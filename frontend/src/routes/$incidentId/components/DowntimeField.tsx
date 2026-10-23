import * as stylex from '@stylexjs/stylex';

import {
  background,
  border,
  content,
  fontWeight,
  radius,
  space,
} from '../../../styles/tokens.stylex';

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
    <div {...stylex.props(styles.row)}>
      <div {...stylex.props(styles.label)}>Downtime</div>
      <div {...stylex.props(styles.value)}>
        {isEditing ? (
          <div {...stylex.props(styles.editor)}>
            <input
              type="number"
              min="0"
              value={draftValue ?? ''}
              onChange={e => {
                const num = e.target.valueAsNumber;
                onChange(e.target.value === '' ? null : Number.isNaN(num) ? null : num);
              }}
              placeholder="—"
              {...stylex.props(styles.input)}
            />
            <span {...stylex.props(styles.unit)}>min</span>
          </div>
        ) : (
          <span
            {...stylex.props(
              styles.displayValue,
              value != null ? styles.presentValue : styles.emptyValue
            )}
          >
            {value != null ? `${value} min` : 'Not set'}
          </span>
        )}
      </div>
    </div>
  );
}

const styles = stylex.create({
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
  editor: {gap: space.xs, display: 'flex', alignItems: 'center'},
  input: {
    appearance: {
      default: 'textfield',
      '::-webkit-inner-spin-button': 'none',
      '::-webkit-outer-spin-button': 'none',
    },
    borderRadius: radius.sm,
    borderColor: border.secondary,
    backgroundColor: background.primary,
    paddingLeft: space.sm,
    paddingRight: space.sm,
    paddingTop: space.xs,
    paddingBottom: space.xs,
    width: '80px',
    borderWidth: '1px',
    borderStyle: 'solid',
    textAlign: 'right',
    fontSize: '14px',
    lineHeight: '20px',
  },
  unit: {color: content.secondary, fontSize: '14px', lineHeight: '20px'},
  displayValue: {fontSize: 14, lineHeight: '20px'},
  presentValue: {color: content.primary},
  emptyValue: {color: content.secondary},
});
