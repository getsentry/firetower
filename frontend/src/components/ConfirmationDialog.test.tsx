import {describe, expect, it, jest} from 'bun:test';

import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import {ConfirmationDialog} from './ConfirmationDialog';

describe('ConfirmationDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Confirm Action',
    message: 'Are you sure you want to proceed?',
    confirmLabel: 'Confirm',
    onConfirm: jest.fn(),
    onCancel: jest.fn(),
  };

  it('renders nothing when closed', () => {
    render(<ConfirmationDialog {...defaultProps} isOpen={false} />);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders dialog when open', () => {
    render(<ConfirmationDialog {...defaultProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('renders title and message', () => {
    render(<ConfirmationDialog {...defaultProps} />);

    expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure you want to proceed?')).toBeInTheDocument();
  });

  it('renders confirm and cancel buttons', () => {
    render(<ConfirmationDialog {...defaultProps} />);

    expect(screen.getByRole('button', {name: 'Confirm'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Cancel'})).toBeInTheDocument();
  });

  it('uses custom cancel label when provided', () => {
    render(<ConfirmationDialog {...defaultProps} cancelLabel="Dismiss" />);

    expect(screen.getByRole('button', {name: 'Dismiss'})).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = jest.fn();

    render(<ConfirmationDialog {...defaultProps} onConfirm={onConfirm} />);

    await user.click(screen.getByRole('button', {name: 'Confirm'}));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = jest.fn();

    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel} />);

    await user.click(screen.getByRole('button', {name: 'Cancel'}));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when overlay is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = jest.fn();

    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel} />);

    const overlay = document.querySelector('[aria-hidden="true"]');
    expect(overlay).toBeInTheDocument();

    await user.click(overlay!);

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when Escape key is pressed', async () => {
    const user = userEvent.setup();
    const onCancel = jest.fn();

    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel} />);

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  it('supports ReactNode as message', () => {
    render(
      <ConfirmationDialog
        {...defaultProps}
        message={
          <div>
            <strong>Warning:</strong> This action cannot be undone.
          </div>
        }
      />
    );

    expect(screen.getByText('Warning:')).toBeInTheDocument();
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument();
  });
});
