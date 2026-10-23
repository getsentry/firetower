import {useState} from 'react';
import type {DateRange} from 'react-day-picker';
import * as stylex from '@stylexjs/stylex';
import {useNavigate} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {DateRangePicker} from 'components/DateRangePicker';
import {Pencil} from 'lucide-react';

import {content, fontSize, space} from '../../../styles/tokens.stylex';
import {useActiveFilters} from '../useActiveFilters';

function toDateString(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function parseDate(dateStr: string | undefined): Date | undefined {
  if (!dateStr) return undefined;
  const match = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return undefined;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function DateRangeFilter() {
  const navigate = useNavigate({from: '/'});
  const {search} = useActiveFilters();
  const [open, setOpen] = useState(false);
  const after = search.created_after;
  const before = search.created_before;

  const value: DateRange | undefined =
    after || before ? {from: parseDate(after), to: parseDate(before)} : undefined;

  const handleChange = (range: DateRange | undefined) => {
    navigate({
      to: '/',
      search: prev => ({
        ...prev,
        created_after: range?.from ? toDateString(range.from) : undefined,
        created_before: range?.to ? toDateString(range.to) : undefined,
      }),
      replace: true,
    });
  };

  const handleClear = () => {
    navigate({
      to: '/',
      search: prev => ({
        ...prev,
        created_after: undefined,
        created_before: undefined,
      }),
      replace: true,
    });
  };

  return (
    <div>
      <div {...stylex.props(styles.heading)}>
        <h3 {...stylex.props(styles.label)}>Created Date</h3>
        <Button
          variant="icon"
          onClick={() => setOpen(true)}
          aria-label="Edit date range"
          style={[open ? styles.hidden : styles.noTransition]}
        >
          <Pencil {...stylex.props(styles.icon)} />
        </Button>
      </div>
      <div {...stylex.props(styles.picker)}>
        <DateRangePicker
          value={value}
          onChange={handleChange}
          onClear={handleClear}
          open={open}
          onOpenChange={setOpen}
          placeholder="Any"
        />
      </div>
    </div>
  );
}

const styles = stylex.create({
  heading: {
    marginBottom: space.md,
    gap: space.xs,
    display: 'flex',
    minHeight: '32px',
    alignItems: 'center',
  },
  label: {fontSize: fontSize.md, color: content.secondary, fontWeight: 600},
  icon: {height: 16, width: 16},
  picker: {display: 'flex', minHeight: '28px', alignItems: 'center'},
  hidden: {visibility: 'hidden'},
  noTransition: {transitionProperty: 'none'},
});
