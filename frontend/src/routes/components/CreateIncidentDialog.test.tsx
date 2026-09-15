import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, describe, expect, it, vi} from 'vitest';

import {CreateIncidentDialog} from './CreateIncidentDialog';

const mockNavigate = vi.fn();
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mockNavigate,
}));

const {mockApiGet, mockApiPost} = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
  mockApiPost: vi.fn(),
}));
vi.mock('../../api', () => ({
  Api: {
    get: mockApiGet,
    post: mockApiPost,
  },
}));

const mockCurrentUser = {
  email: 'test.user@example.com',
  name: 'Test User',
  avatar_url: null,
};

function renderDialog(
  props: {isOpen: boolean; onClose: () => void},
  {withUser = true}: {withUser?: boolean} = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {retry: false},
      mutations: {retry: false},
    },
  });
  if (withUser) {
    queryClient.setQueryData(['CurrentUser'], mockCurrentUser);
  }
  return render(
    <QueryClientProvider client={queryClient}>
      <CreateIncidentDialog {...props} />
    </QueryClientProvider>
  );
}

describe('CreateIncidentDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when closed', () => {
    const {container} = renderDialog({isOpen: false, onClose: vi.fn()});
    expect(container.firstChild).toBeNull();
  });

  it('renders the dialog when open', () => {
    renderDialog({isOpen: true, onClose: vi.fn()});

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Create Incident')).toBeInTheDocument();
    expect(screen.getByLabelText('Title')).toBeInTheDocument();
    expect(screen.getByLabelText('Severity')).toBeInTheDocument();
  });

  it('disables submit when title is empty', () => {
    renderDialog({isOpen: true, onClose: vi.fn()});

    expect(screen.getByRole('button', {name: 'Create'})).toBeDisabled();
  });

  it('enables submit when title is filled', async () => {
    const user = userEvent.setup();
    renderDialog({isOpen: true, onClose: vi.fn()});

    await user.type(screen.getByLabelText('Title'), 'Test incident');

    expect(screen.getByRole('button', {name: 'Create'})).toBeEnabled();
  });

  it('calls onClose and resets fields when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDialog({isOpen: true, onClose});

    await user.type(screen.getByLabelText('Title'), 'Some title');
    await user.click(screen.getByRole('button', {name: 'Cancel'}));

    expect(onClose).toHaveBeenCalled();
  });

  it('creates incident, closes dialog, and navigates on success', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockApiPost.mockResolvedValueOnce({id: 'INC-999', title: 'Test', severity: 'P3'});
    renderDialog({isOpen: true, onClose});

    await user.type(screen.getByLabelText('Title'), 'Test incident');
    await user.click(screen.getByRole('button', {name: 'Create'}));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/incidents/',
        body: expect.objectContaining({
          title: 'Test incident',
          severity: 'P3',
          captain: 'test.user@example.com',
          reporter: 'test.user@example.com',
        }),
      })
    );
    expect(mockNavigate).toHaveBeenCalledWith({
      to: '/$incidentId',
      params: {incidentId: 'INC-999'},
    });
  });

  it('shows error message and does not navigate on failure', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockApiPost.mockRejectedValueOnce(new Error('Server error'));
    renderDialog({isOpen: true, onClose});

    await user.type(screen.getByLabelText('Title'), 'Test incident');
    await user.click(screen.getByRole('button', {name: 'Create'}));

    expect(
      await screen.findByText('Failed to create incident. Please try again.')
    ).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('prevents closing the dialog while mutation is pending', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    let resolvePost: (value: unknown) => void;
    mockApiPost.mockReturnValueOnce(
      new Promise(resolve => {
        resolvePost = resolve;
      })
    );
    renderDialog({isOpen: true, onClose});

    await user.type(screen.getByLabelText('Title'), 'Test incident');
    await user.click(screen.getByRole('button', {name: 'Create'}));

    // Dialog should still be open — Cancel should not close while pending
    await user.click(screen.getByRole('button', {name: 'Cancel'}));
    expect(onClose).not.toHaveBeenCalled();

    // Resolve the mutation to clean up
    resolvePost!({id: 'INC-999', title: 'Test', severity: 'P3'});
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('disables submit when currentUser is not loaded', async () => {
    const user = userEvent.setup();
    renderDialog({isOpen: true, onClose: vi.fn()}, {withUser: false});

    await user.type(screen.getByLabelText('Title'), 'Test incident');

    expect(screen.getByRole('button', {name: 'Create'})).toBeDisabled();
  });

  it('prevents overlay click from closing dialog while pending', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    let resolvePost: (value: unknown) => void;
    mockApiPost.mockReturnValueOnce(
      new Promise(resolve => {
        resolvePost = resolve;
      })
    );
    renderDialog({isOpen: true, onClose});

    await user.type(screen.getByLabelText('Title'), 'Test incident');
    await user.click(screen.getByRole('button', {name: 'Create'}));

    // Click overlay — should not close
    const overlay = screen.getByRole('dialog').previousElementSibling as HTMLElement;
    await user.click(overlay);
    expect(onClose).not.toHaveBeenCalled();

    resolvePost!({id: 'INC-999', title: 'Test', severity: 'P3'});
    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });
});
