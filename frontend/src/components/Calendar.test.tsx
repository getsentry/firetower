import {useState} from 'react';
import type {DateRange} from 'react-day-picker';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, vi} from 'vitest';

import {Calendar} from './Calendar';

const october = new Date(2026, 9, 1);

describe('Calendar', () => {
  it('selects a day and preserves keyboard focus movement', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Calendar mode="single" defaultMonth={october} onSelect={onSelect} />);
    const day = screen.getByRole('button', {name: /October 20th, 2026/});
    await user.click(day);
    expect(onSelect.mock.calls[0][0]).toEqual(new Date(2026, 9, 20));
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('button', {name: /October 21st, 2026/})).toHaveFocus();
  });

  it('selects a range and marks both endpoints and middle days selected', async () => {
    const user = userEvent.setup();
    function RangeCalendar() {
      const [selected, setSelected] = useState<DateRange>();
      return (
        <Calendar
          mode="range"
          defaultMonth={october}
          selected={selected}
          onSelect={setSelected}
        />
      );
    }
    render(<RangeCalendar />);
    await user.click(screen.getByRole('button', {name: /October 12th, 2026/}));
    await user.click(screen.getByRole('button', {name: /October 16th, 2026/}));
    for (const day of ['12th', '14th', '16th']) {
      expect(
        screen
          .getByRole('button', {name: new RegExp(`October ${day}, 2026`)})
          .closest('td')
      ).toHaveAttribute('aria-selected', 'true');
    }
    expect(
      screen.getByRole('button', {name: /October 17th, 2026/}).closest('td')
    ).not.toHaveAttribute('aria-selected');
  });

  it('preserves dropdown navigation, week numbers, RTL, outside and disabled days', async () => {
    const user = userEvent.setup();
    render(
      <Calendar
        mode="single"
        defaultMonth={october}
        captionLayout="dropdown"
        showWeekNumber
        dir="rtl"
        disabled={new Date(2026, 9, 20)}
        startMonth={new Date(2025, 0)}
        endMonth={new Date(2027, 11)}
      />
    );
    expect(screen.getByRole('button', {name: /October 20th, 2026/})).toBeDisabled();
    expect(
      screen.getByRole('button', {name: /September 30th, 2026/}).closest('td')
    ).toHaveAttribute('data-outside', 'true');
    expect(screen.getByLabelText('Week Number')).toBeInTheDocument();
    expect(screen.getByRole('grid').closest('[dir]')).toHaveAttribute('dir', 'rtl');
    await user.selectOptions(
      screen.getByRole('combobox', {name: /Choose the Month/}),
      '10'
    );
    expect(screen.getByRole('button', {name: /November 20th, 2026/})).toBeInTheDocument();
    await user.selectOptions(
      screen.getByRole('combobox', {name: /Choose the Year/}),
      '2025'
    );
    expect(screen.getByRole('button', {name: /November 20th, 2025/})).toBeInTheDocument();
    await user.click(screen.getByRole('button', {name: /Go to the Next Month/}));
    expect(screen.getByRole('button', {name: /December 20th, 2025/})).toBeInTheDocument();
  });
});
