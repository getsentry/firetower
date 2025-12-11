import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen} from '@testing-library/react';
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
});
