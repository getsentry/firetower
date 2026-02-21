import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it, jest} from 'bun:test';

import {EditableTags} from './EditableTags';

const suggestions = ['API', 'Database', 'Frontend', 'Backend', 'Infrastructure'];

describe('EditableTags', () => {
  it('renders tags', async () => {
    render(
      <EditableTags
        tags={['API', 'Database']}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    expect(await screen.findByText('API')).toBeInTheDocument();
    expect(await screen.findByText('Database')).toBeInTheDocument();
  });

  it('shows empty text when no tags', async () => {
    render(
      <EditableTags
        tags={[]}
        suggestions={suggestions}
        onSave={async () => {}}
        emptyText="No tags yet"
      />
    );

    expect(await screen.findByText('No tags yet')).toBeInTheDocument();
  });

  it('opens editing mode when edit button clicked', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={['API']}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    expect(await screen.findByRole('textbox')).toBeInTheDocument();
    expect(await screen.findByRole('button', {name: 'Save'})).toBeInTheDocument();
    expect(await screen.findByRole('button', {name: 'Cancel'})).toBeInTheDocument();
  });

  it('shows suggestions when editing', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={[]}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    for (const suggestion of suggestions) {
      expect(await screen.findByRole('button', {name: suggestion})).toBeInTheDocument();
    }
  });

  it('can add a tag from suggestions', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={[]}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    const apiButton = await screen.findByRole('button', {name: 'API'});
    await user.click(apiButton);

    // Tag should now appear in the draft list with a remove button
    expect(await screen.findByRole('button', {name: 'Remove API'})).toBeInTheDocument();
  });

  it('can remove a tag', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={['API', 'Database']}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    const removeButton = await screen.findByRole('button', {name: 'Remove API'});
    await user.click(removeButton);

    expect(screen.queryByRole('button', {name: 'Remove API'})).not.toBeInTheDocument();
    expect(
      await screen.findByRole('button', {name: 'Remove Database'})
    ).toBeInTheDocument();
  });

  it('calls onSave with updated tags', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});

    render(
      <EditableTags
        label="Categories"
        tags={['API']}
        suggestions={suggestions}
        onSave={onSave}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    const databaseButton = await screen.findByRole('button', {name: 'Database'});
    await user.click(databaseButton);

    const saveButton = await screen.findByRole('button', {name: 'Save'});
    await user.click(saveButton);

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(['API', 'Database']);
    });
  });

  it('cancels editing on escape', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={['API']}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    expect(await screen.findByRole('textbox')).toBeInTheDocument();

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  it('filters suggestions based on input', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={[]}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    const input = await screen.findByRole('textbox');
    await user.type(input, 'Front');

    expect(await screen.findByRole('button', {name: 'Frontend'})).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'API'})).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Backend'})).not.toBeInTheDocument();
  });

  it('shows empty state when no suggestions match', async () => {
    const user = userEvent.setup();

    render(
      <EditableTags
        label="Categories"
        tags={[]}
        suggestions={suggestions}
        onSave={async () => {}}
      />
    );

    const editButton = await screen.findByRole('button', {name: 'Edit Categories'});
    await user.click(editButton);

    const input = await screen.findByRole('textbox');
    await user.type(input, 'xyz');

    expect(await screen.findByText('No tags match that query.')).toBeInTheDocument();
  });
});
