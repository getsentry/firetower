import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

import {ParticipantsList} from './ParticipantsList';

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {retry: false},
      mutations: {retry: false},
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockParticipants: IncidentDetail['participants'] = [
  {
    name: 'John Smith',
    avatar_url: null,
    role: 'Captain',
    email: 'john.smith@example.com',
  },
  {name: 'Jane Doe', avatar_url: null, role: 'Reporter', email: 'jane.doe@example.com'},
  {
    name: 'Alice Brown',
    avatar_url: null,
    role: 'Participant',
    email: 'alice.brown@example.com',
  },
  {
    name: 'Charlie Davis',
    avatar_url: null,
    role: 'Participant',
    email: 'charlie.davis@example.com',
  },
  {
    name: 'Eva Foster',
    avatar_url: null,
    role: 'Participant',
    email: 'eva.foster@example.com',
  },
  {
    name: 'Frank Garcia',
    avatar_url: null,
    role: 'Participant',
    email: 'frank.garcia@example.com',
  },
  {
    name: 'Grace Lee',
    avatar_url: null,
    role: 'Participant',
    email: 'grace.lee@example.com',
  },
  {
    name: 'Henry Wilson',
    avatar_url: null,
    role: 'Participant',
    email: 'henry.wilson@example.com',
  },
];

describe('ParticipantsList', () => {
  it('shows edit button for captain and reporter roles', () => {
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    expect(screen.getByRole('button', {name: 'Edit Captain'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Edit Reporter'})).toBeInTheDocument();
  });

  it('enters edit mode when clicking edit button', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));

    // Should show search input and cancel button
    expect(screen.getByRole('button', {name: 'Cancel'})).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toHaveAttribute('placeholder', 'John Smith');
  });

  it('shows dropdown immediately when entering edit mode', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));

    expect(screen.getByRole('listbox')).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('closes edit mode when clicking cancel button', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));
    expect(screen.getByRole('button', {name: 'Cancel'})).toBeInTheDocument();

    await user.click(screen.getByRole('button', {name: 'Cancel'}));
    expect(screen.queryByRole('button', {name: 'Cancel'})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Edit Captain'})).toBeInTheDocument();
  });

  it('deduplicates dropdown when captain and reporter are same person', async () => {
    const user = userEvent.setup();
    const samePersonParticipants: IncidentDetail['participants'] = [
      {name: 'John Smith', avatar_url: null, role: 'Captain', email: 'john@example.com'},
      {name: 'John Smith', avatar_url: null, role: 'Reporter', email: 'john@example.com'},
      {
        name: 'Jane Doe',
        avatar_url: null,
        role: 'Participant',
        email: 'jane@example.com',
      },
    ];

    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={samePersonParticipants} />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));

    // Should only show 2 options (deduplicated), not 3
    expect(screen.getAllByRole('option')).toHaveLength(2);
  });

  it('returns null when participants array is empty', () => {
    const {container} = renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={[]} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders all participants when 5 or fewer', () => {
    const fiveParticipants = mockParticipants.slice(0, 5);
    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={fiveParticipants} />
    );

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Eva Foster')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {name: /show.*participants/i})
    ).not.toBeInTheDocument();
  });

  it('shows only first 5 participants when more than 5 exist', () => {
    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={mockParticipants} />
    );

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Eva Foster')).toBeInTheDocument();
    expect(screen.queryByText('Frank Garcia')).not.toBeInTheDocument();
    expect(screen.queryByText('Grace Lee')).not.toBeInTheDocument();
    expect(screen.queryByText('Henry Wilson')).not.toBeInTheDocument();
  });

  it('shows "Show X more participants" button when more than 5 participants', () => {
    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={mockParticipants} />
    );

    expect(
      screen.getByRole('button', {name: 'Show 3 more participants'})
    ).toBeInTheDocument();
  });

  it('expands to show all participants when button is clicked', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={mockParticipants} />
    );

    await user.click(screen.getByRole('button', {name: 'Show 3 more participants'}));

    expect(screen.getByText('Frank Garcia')).toBeInTheDocument();
    expect(screen.getByText('Grace Lee')).toBeInTheDocument();
    expect(screen.getByText('Henry Wilson')).toBeInTheDocument();
    expect(
      screen.getByRole('button', {name: 'Show fewer participants'})
    ).toBeInTheDocument();
  });

  it('collapses back to 5 participants when "Show fewer" is clicked', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList incidentId="INC-123" participants={mockParticipants} />
    );

    await user.click(screen.getByRole('button', {name: 'Show 3 more participants'}));
    await user.click(screen.getByRole('button', {name: 'Show fewer participants'}));

    expect(screen.queryByText('Frank Garcia')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', {name: 'Show 3 more participants'})
    ).toBeInTheDocument();
  });

  it('displays participant roles for non-Participant roles', () => {
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    expect(screen.getByText('Captain')).toBeInTheDocument();
    expect(screen.getByText('Reporter')).toBeInTheDocument();
    expect(screen.queryByText('Participant')).not.toBeInTheDocument();
  });

  it('filters participants by search input', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 5)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));
    await user.type(screen.getByRole('textbox'), 'Jane');

    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(1);
    expect(options[0]).toHaveTextContent('Jane Doe');
  });

  it('shows empty state when search matches no participants', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));
    await user.type(screen.getByRole('textbox'), 'zzzzz');

    expect(screen.queryAllByRole('option')).toHaveLength(0);
    expect(screen.getByText('No participants match')).toBeInTheDocument();
  });

  it('selects participant via keyboard navigation', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(
      <ParticipantsList
        incidentId="INC-123"
        participants={mockParticipants.slice(0, 3)}
      />
    );

    await user.click(screen.getByRole('button', {name: 'Edit Captain'}));
    const input = screen.getByRole('textbox');

    await user.type(input, '{arrowdown}{arrowdown}{enter}');

    // After selection, the async mutation resolves/rejects and edit mode closes
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });
});
