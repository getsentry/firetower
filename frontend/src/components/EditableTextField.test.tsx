import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, jest} from 'bun:test';
import {z} from 'zod';

import {EditableTextField} from './EditableTextField';

describe('EditableTextField', () => {
  it('renders display value', async () => {
    render(<EditableTextField value="Test value" onSave={async () => {}} />);

    const display = await screen.findByText('Test value');
    expect(display).toBeInTheDocument();
  });

  it('shows trigger button when editable', async () => {
    render(<EditableTextField value="Test" onSave={async () => {}} editable={true} />);

    const trigger = await screen.findByLabelText('Edit');
    expect(trigger).toBeInTheDocument();
  });

  it('hides trigger button when not editable', async () => {
    render(<EditableTextField value="Test" onSave={async () => {}} editable={false} />);

    const trigger = screen.queryByLabelText('Edit');
    expect(trigger).not.toBeInTheDocument();
  });

  it('enters edit mode when trigger is clicked', async () => {
    const user = userEvent.setup();

    render(<EditableTextField value="Test" onSave={async () => {}} />);

    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    const input = await screen.findByDisplayValue('Test');
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('Test');
  });

  it('calls onSave with new value when save button is clicked', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(<EditableTextField value="Original" onSave={onSave} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByDisplayValue('Original');
    await user.clear(input);
    await user.type(input, 'Updated');

    // Save
    const saveButton = await screen.findByText('Save');
    await user.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('Updated');
    });
  });

  it('cancels edit mode when cancel button is clicked', async () => {
    const user = userEvent.setup();

    render(<EditableTextField value="Original" onSave={async () => {}} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByDisplayValue('Original');
    await user.type(input, ' Changed');

    // Cancel
    const cancelButton = await screen.findByText('Cancel');
    await user.click(cancelButton);

    // Should exit edit mode
    await waitFor(() => {
      expect(screen.queryByDisplayValue('Original Changed')).not.toBeInTheDocument();
    });
  });

  it('shows validation error when validation fails', async () => {
    const user = userEvent.setup();

    render(
      <EditableTextField
        value="Test"
        onSave={async () => {}}
        validationSchema={z.string().min(5, 'Must be at least 5 characters')}
      />
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Enter invalid text (too short)
    const input = await screen.findByDisplayValue('Test');
    await user.clear(input);
    await user.type(input, 'Hi');

    // Try to save
    const saveButton = await screen.findByText('Save');
    await user.click(saveButton);

    // Should show validation error
    const error = await screen.findByText('Must be at least 5 characters');
    expect(error).toBeInTheDocument();

    // Should stay in edit mode
    expect(input).toBeInTheDocument();
  });

  it('shows error message when save fails', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {
      throw new Error('Save failed');
    });

    render(<EditableTextField value="Test" onSave={onSave} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit the text
    const input = await screen.findByDisplayValue('Test');
    await user.type(input, ' Updated');

    // Try to save
    const saveButton = await screen.findByText('Save');
    await user.click(saveButton);

    // Should show error
    await waitFor(() => {
      const error = screen.getByRole('alert');
      expect(error).toBeInTheDocument();
      expect(error).toHaveTextContent('Save failed');
    });

    // Should stay in edit mode
    expect(input).toBeInTheDocument();
  });

  it('supports multiline mode with textarea', async () => {
    const user = userEvent.setup();

    render(<EditableTextField value="Line 1" onSave={async () => {}} multiline={true} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Should render textarea
    const textarea = await screen.findByDisplayValue('Line 1');
    expect(textarea.tagName).toBe('TEXTAREA');
  });

  it('does not call onSave when value has not changed', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(<EditableTextField value="Unchanged" onSave={onSave} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Save without changes
    const saveButton = await screen.findByText('Save');
    await user.click(saveButton);

    // Should not call onSave
    expect(onSave).not.toHaveBeenCalled();

    // Should exit edit mode
    await waitFor(() => {
      expect(screen.queryByDisplayValue('Unchanged')).not.toBeInTheDocument();
    });
  });

  it('shows saving state while save is in progress', async () => {
    const user = userEvent.setup();
    let resolveSave: () => void;
    const savePromise = new Promise<void>(resolve => {
      resolveSave = resolve;
    });
    const onSave = jest.fn(async () => savePromise);

    render(<EditableTextField value="Test" onSave={onSave} />);

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByDisplayValue('Test');
    await user.type(input, ' Updated');

    // Click save
    const saveButton = await screen.findByText('Save');
    await user.click(saveButton);

    // Should show saving state
    const savingButton = await screen.findByText('Saving...');
    expect(savingButton).toBeInTheDocument();

    // Resolve save
    resolveSave!();

    // Should exit edit mode
    await waitFor(() => {
      expect(screen.queryByDisplayValue('Test Updated')).not.toBeInTheDocument();
    });
  });

  it('renders with custom HTML element', async () => {
    render(<EditableTextField value="Heading" onSave={async () => {}} as="h2" />);

    const heading = await screen.findByText('Heading');
    expect(heading.tagName).toBe('H2');
  });
});
