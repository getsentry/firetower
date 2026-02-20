import {describe, expect, it, jest} from 'bun:test';

import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

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

  it('calls onSave when closed via escape', async () => {
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

    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(['API', 'Database']);
    });
  });

  it('closes editing on escape', async () => {
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

  it('maintains alphabetical sort order throughout editing flow', async () => {
    const user = userEvent.setup();
    const onSave = jest.fn(async () => {});
    const unsortedSuggestions = ['Zebra', 'Mango', 'Apple', 'Banana'];

    // Start with unsorted tags
    const {rerender} = render(
      <EditableTags
        label="Tags"
        tags={['Zebra', 'Mango']}
        suggestions={unsortedSuggestions}
        onSave={onSave}
      />
    );

    // Initial display should show tags sorted, even though props are unsorted
    const initialTags = screen.getAllByText(/Zebra|Mango/);
    expect(initialTags.map(el => el.textContent)).toEqual(['Mango', 'Zebra']);

    // Open editor
    const editButton = await screen.findByRole('button', {name: 'Edit Tags'});
    await user.click(editButton);

    // In editing mode, tags should be sorted
    const editingTags = screen
      .getAllByRole('button', {name: /Remove/})
      .map(btn => btn.getAttribute('aria-label')?.replace('Remove ', ''));
    expect(editingTags).toEqual(['Mango', 'Zebra']);

    // Add 'Apple' which should sort to the front
    const appleButton = await screen.findByRole('button', {name: 'Apple'});
    await user.click(appleButton);

    const afterAddTags = screen
      .getAllByRole('button', {name: /Remove/})
      .map(btn => btn.getAttribute('aria-label')?.replace('Remove ', ''));
    expect(afterAddTags).toEqual(['Apple', 'Mango', 'Zebra']);

    // Close via escape
    await user.keyboard('{Escape}');

    // Check what was passed to onSave
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(['Apple', 'Mango', 'Zebra']);
    });

    // Simulate parent updating tags prop with the saved value (as optimistic update would)
    rerender(
      <EditableTags
        label="Tags"
        tags={['Apple', 'Mango', 'Zebra']}
        suggestions={unsortedSuggestions}
        onSave={onSave}
      />
    );

    // After close, displayed tags should be sorted
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });

    const finalTags = screen.getAllByText(/Apple|Mango|Zebra/);
    expect(finalTags.map(el => el.textContent)).toEqual(['Apple', 'Mango', 'Zebra']);
  });
});
