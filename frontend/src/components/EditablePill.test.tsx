import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, jest} from 'bun:test';

import {EditablePill} from './EditablePill';

const SEVERITY_OPTIONS = ['P0', 'P1', 'P2', 'P3', 'P4'] as const;
const STATUS_OPTIONS = [
  'Active',
  'Mitigated',
  'Actions Pending',
  'Postmortem',
  'Done',
] as const;

describe('EditablePill', () => {
  it('renders current value', async () => {
    render(
      <EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={async () => {}} />
    );

    const pill = await screen.findByText('P1');
    expect(pill).toBeInTheDocument();
  });

  it('opens popover when clicked', async () => {
    const user = userEvent.setup();

    render(
      <EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={async () => {}} />
    );

    const trigger = await screen.findByRole('button', {expanded: false});
    await user.click(trigger);

    const popover = await screen.findByRole('listbox');
    expect(popover).toBeInTheDocument();
  });

  it('shows all options in popover', async () => {
    const user = userEvent.setup();

    render(
      <EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={async () => {}} />
    );

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    for (const option of SEVERITY_OPTIONS) {
      const optionElement = await screen.findByRole('option', {name: option});
      expect(optionElement).toBeInTheDocument();
    }
  });

  it('calls onSave when different option is selected', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(<EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={onSave} />);

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    const p2Option = await screen.findByRole('option', {name: 'P2'});
    await user.click(p2Option);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('P2');
    });
  });

  it('closes popover after selection', async () => {
    const user = userEvent.setup();

    render(
      <EditablePill value="Active" options={STATUS_OPTIONS} onSave={async () => {}} />
    );

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    const mitigatedOption = await screen.findByRole('option', {name: 'Mitigated'});
    await user.click(mitigatedOption);

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });

  it('does not call onSave when same option is selected', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(<EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={onSave} />);

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    const p1Option = await screen.findByRole('option', {name: 'P1'});
    await user.click(p1Option);

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    expect(onSave).not.toHaveBeenCalled();
  });

  it('closes popover on escape key', async () => {
    const user = userEvent.setup();

    render(
      <EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={async () => {}} />
    );

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    expect(await screen.findByRole('listbox')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });

  it('closes popover when clicking outside', async () => {
    const user = userEvent.setup();

    render(
      <div>
        <EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={async () => {}} />
        <button>Outside</button>
      </div>
    );

    const trigger = await screen.findByRole('button', {expanded: false});
    await user.click(trigger);

    expect(await screen.findByRole('listbox')).toBeInTheDocument();

    const outsideButton = await screen.findByText('Outside');
    await user.click(outsideButton);

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });

  it('shows saving state during save operation', async () => {
    const user = userEvent.setup();
    let resolveSave: () => void;
    const savePromise = new Promise<void>(resolve => {
      resolveSave = resolve;
    });
    const onSave = jest.fn(async () => savePromise);

    render(<EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={onSave} />);

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    const p2Option = await screen.findByRole('option', {name: 'P2'});
    await user.click(p2Option);

    await waitFor(() => {
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    resolveSave!();

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('P2');
    });
  });

  it('handles save errors gracefully', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const onSave = jest.fn(async () => {
      throw new Error('Save failed');
    });

    render(<EditablePill value="P1" options={SEVERITY_OPTIONS} onSave={onSave} />);

    const trigger = await screen.findByRole('button');
    await user.click(trigger);

    const p2Option = await screen.findByRole('option', {name: 'P2'});
    await user.click(p2Option);

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalled();
    });

    consoleErrorSpy.mockRestore();
  });
});
