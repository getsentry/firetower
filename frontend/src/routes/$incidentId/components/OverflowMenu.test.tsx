import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, jest} from 'bun:test';

import {OverflowMenu} from './OverflowMenu';

describe('OverflowMenu', () => {
  it('renders trigger button', () => {
    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    expect(screen.getByRole('button', {name: 'More actions'})).toBeInTheDocument();
  });

  it('opens menu when trigger is clicked', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));

    expect(screen.getByRole('menu')).toBeInTheDocument();
  });

  it('shows "Convert to private incident" when incident is public', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));

    expect(
      screen.getByRole('menuitem', {name: 'Convert to private incident'})
    ).toBeInTheDocument();
  });

  it('shows "Make incident public" when incident is private', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={true} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));

    expect(
      screen.getByRole('menuitem', {name: 'Make incident public'})
    ).toBeInTheDocument();
  });

  it('shows confirmation dialog when menu item is clicked', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Convert to private incident?')).toBeInTheDocument();
  });

  it('shows correct confirmation message for public to private', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));

    expect(
      screen.getByText('This incident will only be visible to participants and admins.')
    ).toBeInTheDocument();
  });

  it('shows correct confirmation message for private to public', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={true} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Make incident public'}));

    expect(
      screen.getByText('This incident will be visible to all users.')
    ).toBeInTheDocument();
  });

  it('calls onToggleVisibility when confirmed', async () => {
    const user = userEvent.setup();
    const onToggleVisibility = jest.fn(async () => {});

    render(<OverflowMenu isPrivate={false} onToggleVisibility={onToggleVisibility} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));
    await user.click(screen.getByRole('button', {name: 'Convert to private'}));

    await waitFor(() => {
      expect(onToggleVisibility).toHaveBeenCalledTimes(1);
    });
  });

  it('does not call onToggleVisibility when cancelled', async () => {
    const user = userEvent.setup();
    const onToggleVisibility = jest.fn(async () => {});

    render(<OverflowMenu isPrivate={false} onToggleVisibility={onToggleVisibility} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));
    await user.click(screen.getByRole('button', {name: 'Cancel'}));

    expect(onToggleVisibility).not.toHaveBeenCalled();
  });

  it('closes menu when clicking outside', async () => {
    const user = userEvent.setup();

    render(
      <div>
        <OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />
        <button>Outside</button>
      </div>
    );

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    await user.click(screen.getByText('Outside'));

    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
  });

  it('closes dialog when cancelled', async () => {
    const user = userEvent.setup();

    render(<OverflowMenu isPrivate={false} onToggleVisibility={async () => {}} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.click(screen.getByRole('button', {name: 'Cancel'}));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('handles errors gracefully', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const onToggleVisibility = jest.fn(async () => {
      throw new Error('Toggle failed');
    });

    render(<OverflowMenu isPrivate={false} onToggleVisibility={onToggleVisibility} />);

    await user.click(screen.getByRole('button', {name: 'More actions'}));
    await user.click(screen.getByRole('menuitem', {name: 'Convert to private incident'}));
    await user.click(screen.getByRole('button', {name: 'Convert to private'}));

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalled();
    });

    consoleErrorSpy.mockRestore();
  });
});
