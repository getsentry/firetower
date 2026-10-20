import {useState} from 'react';
import type {DateRange} from 'react-day-picker';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, vi} from 'vitest';

import {DateRangePicker} from './DateRangePicker';

function Picker({onClear}: {onClear: () => void}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState<DateRange | undefined>({
    from: new Date(2026, 9, 12),
    to: new Date(2026, 9, 16),
  });
  return (
    <DateRangePicker
      value={value}
      onChange={setValue}
      open={open}
      onOpenChange={setOpen}
      onClear={() => {
        setValue(undefined);
        onClear();
      }}
      numberOfMonths={1}
    />
  );
}

describe('DateRangePicker', () => {
  it('opens with the keyboard and returns focus to the native trigger on escape', async () => {
    const user = userEvent.setup();
    render(<Picker onClear={vi.fn()} />);
    const trigger = screen.getByRole('button', {name: /Oct 12, 2026/});
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('clears without opening the calendar and focuses the remaining trigger', async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    render(<Picker onClear={onClear} />);
    await user.click(screen.getByRole('button', {name: 'Clear date range'}));
    expect(onClear).toHaveBeenCalledOnce();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Pick a date range'})).toHaveFocus();
  });
});
