import {useState} from 'react';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, vi} from 'vitest';

import {SearchableSelect} from './SearchableSelect';

const OPTIONS = [
  {value: 'all', label: 'All teams'},
  {value: 'eng', label: 'Engineering', description: 'ENG · 4 open'},
  {value: 'infra', label: 'Infrastructure', description: 'INFRA · 2 open'},
];

function Example({onChange}: {onChange: (value: string) => void}) {
  const [value, setValue] = useState('all');
  return (
    <SearchableSelect
      label="Team"
      value={value}
      options={OPTIONS}
      onChange={next => {
        setValue(next);
        onChange(next);
      }}
    />
  );
}

function setup() {
  const onChange = vi.fn();
  render(<Example onChange={onChange} />);
  return {user: userEvent.setup(), onChange};
}

describe('SearchableSelect', () => {
  it('uses one button surface without an inset tag and focuses a searchable listbox', async () => {
    const {user} = setup();
    const trigger = screen.getByRole('combobox', {name: 'Team'});
    expect(trigger).toHaveTextContent('All teams');
    expect(trigger.firstElementChild).toBe(screen.getByText('All teams'));
    expect(trigger.firstElementChild?.childElementCount).toBe(0);
    expect(trigger.lastElementChild?.tagName.toLowerCase()).toBe('svg');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(document.querySelector('select')).toBeNull();
    await user.click(trigger);
    expect(screen.getByRole('textbox', {name: 'Search Team'})).toHaveFocus();
    expect(screen.getByRole('listbox', {name: 'Team'})).toBeInTheDocument();
    expect(screen.getByRole('option', {name: 'All teams'})).toHaveAttribute(
      'aria-selected',
      'true'
    );
  });

  it('searches labels and secondary identifiers and commits a selection', async () => {
    const {user, onChange} = setup();
    await user.click(screen.getByRole('combobox', {name: 'Team'}));
    await user.type(screen.getByRole('textbox', {name: 'Search Team'}), 'infra');
    expect(screen.queryByRole('option', {name: /^Engineering/})).not.toBeInTheDocument();
    await user.click(screen.getByRole('option', {name: /^Infrastructure/}));
    expect(onChange).toHaveBeenCalledExactlyOnceWith('infra');
    expect(screen.getByRole('combobox', {name: 'Team'})).toHaveTextContent(
      'Infrastructure'
    );
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', {name: 'Team'})).toHaveFocus();
  });

  it('supports keyboard opening, navigation, wrapping, and selection', async () => {
    const {user, onChange} = setup();
    screen.getByRole('combobox', {name: 'Team'}).focus();
    await user.keyboard('{ArrowDown}');
    const input = screen.getByRole('textbox', {name: 'Search Team'});
    expect(input).toHaveFocus();
    await user.keyboard('{ArrowUp}');
    const option = screen.getByRole('option', {name: /^Infrastructure/});
    expect(input).toHaveAttribute('aria-activedescendant', option.id);
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('infra');
  });

  it('closes on Escape without changing the selection and resets search', async () => {
    const {user, onChange} = setup();
    const trigger = screen.getByRole('combobox', {name: 'Team'});
    await user.click(trigger);
    await user.type(screen.getByRole('textbox', {name: 'Search Team'}), 'eng');
    await user.keyboard('{Escape}');
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger).toHaveTextContent('All teams');
    expect(trigger).toHaveFocus();
    await user.click(trigger);
    expect(screen.getByRole('textbox', {name: 'Search Team'})).toHaveValue('');
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('handles empty results without committing an undefined value', async () => {
    const {user, onChange} = setup();
    await user.click(screen.getByRole('combobox', {name: 'Team'}));
    await user.type(screen.getByRole('textbox', {name: 'Search Team'}), 'missing');
    expect(screen.getByRole('status')).toHaveTextContent('No matches found');
    expect(screen.queryByRole('option')).not.toBeInTheDocument();
    await user.keyboard('{ArrowDown}{Enter}');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('does not fire changes when choosing the current value', async () => {
    const {user, onChange} = setup();
    await user.click(screen.getByRole('combobox', {name: 'Team'}));
    await user.click(screen.getByRole('option', {name: 'All teams'}));
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('does not submit a surrounding form when selecting with Enter', async () => {
    const onSubmit = vi.fn(event => event.preventDefault());
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <form onSubmit={onSubmit}>
        <SearchableSelect
          label="Team"
          value="all"
          options={OPTIONS}
          onChange={onChange}
        />
      </form>
    );
    await user.click(screen.getByRole('combobox', {name: 'Team'}));
    await user.type(screen.getByRole('textbox', {name: 'Search Team'}), 'Engineering');
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith('eng');
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
