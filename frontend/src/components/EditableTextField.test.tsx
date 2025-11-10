import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, jest} from 'bun:test';
import {z} from 'zod';

import {EditableTextField} from './EditableTextField';

describe('EditableTextField', () => {
  it('renders display value', async () => {
    render(
      <EditableTextField value="Test value" onSave={async () => {}}>
        <EditableTextField.Display>Test value</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    const display = await screen.findByText('Test value');
    expect(display).toBeInTheDocument();
  });

  it('shows trigger button when editable', async () => {
    render(
      <EditableTextField value="Test" onSave={async () => {}} editable={true}>
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    const trigger = await screen.findByLabelText('Edit');
    expect(trigger).toBeInTheDocument();
  });

  it('hides trigger button when not editable', async () => {
    render(
      <EditableTextField value="Test" onSave={async () => {}} editable={false}>
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    const trigger = screen.queryByLabelText('Edit');
    expect(trigger).not.toBeInTheDocument();
  });

  it('enters edit mode when trigger is clicked', async () => {
    const user = userEvent.setup();

    render(
      <EditableTextField value="Test" onSave={async () => {}}>
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    const input = await screen.findByPlaceholderText('Enter text');
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('Test');
  });

  it('calls onSave with new value when save button is clicked', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(
      <EditableTextField value="Original" onSave={onSave}>
        <EditableTextField.Display>Original</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByPlaceholderText('Enter text');
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

    render(
      <EditableTextField value="Original" onSave={async () => {}}>
        <EditableTextField.Display>Original</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByPlaceholderText('Enter text');
    await user.type(input, ' Changed');

    // Cancel
    const cancelButton = await screen.findByText('Cancel');
    await user.click(cancelButton);

    // Should exit edit mode
    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Enter text')).not.toBeInTheDocument();
    });
  });

  it('shows validation error when validation fails', async () => {
    const user = userEvent.setup();

    render(
      <EditableTextField
        value="Test"
        onSave={async () => {}}
        validationSchema={z.string().min(5, 'Must be at least 5 characters')}
      >
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Enter invalid text (too short)
    const input = await screen.findByPlaceholderText('Enter text');
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

    render(
      <EditableTextField value="Test" onSave={onSave}>
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit the text
    const input = await screen.findByPlaceholderText('Enter text');
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

    render(
      <EditableTextField value="Line 1" onSave={async () => {}} multiline={true}>
        <EditableTextField.Display>Line 1</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Should render textarea
    const textarea = await screen.findByPlaceholderText('Enter text');
    expect(textarea.tagName).toBe('TEXTAREA');
  });

  it('does not call onSave when value has not changed', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(
      <EditableTextField value="Unchanged" onSave={onSave}>
        <EditableTextField.Display>Unchanged</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

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
      expect(screen.queryByPlaceholderText('Enter text')).not.toBeInTheDocument();
    });
  });

  it('shows saving state while save is in progress', async () => {
    const user = userEvent.setup();
    let resolveSave: () => void;
    const savePromise = new Promise<void>(resolve => {
      resolveSave = resolve;
    });
    const onSave = jest.fn(async () => savePromise);

    render(
      <EditableTextField value="Test" onSave={onSave}>
        <EditableTextField.Display>Test</EditableTextField.Display>
        <EditableTextField.Trigger />
        <EditableTextField.Input placeholder="Enter text" />
        <EditableTextField.Actions />
      </EditableTextField>
    );

    // Enter edit mode
    const trigger = await screen.findByLabelText('Edit');
    await user.click(trigger);

    // Edit text
    const input = await screen.findByPlaceholderText('Enter text');
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
      expect(screen.queryByPlaceholderText('Enter text')).not.toBeInTheDocument();
    });
  });
});
