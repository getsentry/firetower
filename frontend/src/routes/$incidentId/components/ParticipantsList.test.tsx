import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

import {ParticipantsList} from './ParticipantsList';

const mockParticipants: IncidentDetail['participants'] = [
  {name: 'John Smith', avatar_url: null, role: 'Captain'},
  {name: 'Jane Doe', avatar_url: null, role: 'Reporter'},
  {name: 'Alice Brown', avatar_url: null, role: 'Participant'},
  {name: 'Charlie Davis', avatar_url: null, role: 'Participant'},
  {name: 'Eva Foster', avatar_url: null, role: 'Participant'},
  {name: 'Frank Garcia', avatar_url: null, role: 'Participant'},
  {name: 'Grace Lee', avatar_url: null, role: 'Participant'},
  {name: 'Henry Wilson', avatar_url: null, role: 'Participant'},
];

describe('ParticipantsList', () => {
  it('returns null when participants array is empty', () => {
    const {container} = render(<ParticipantsList participants={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders all participants when 5 or fewer', () => {
    const fiveParticipants = mockParticipants.slice(0, 5);
    render(<ParticipantsList participants={fiveParticipants} />);

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Eva Foster')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows only first 5 participants when more than 5 exist', () => {
    render(<ParticipantsList participants={mockParticipants} />);

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Eva Foster')).toBeInTheDocument();
    expect(screen.queryByText('Frank Garcia')).not.toBeInTheDocument();
    expect(screen.queryByText('Grace Lee')).not.toBeInTheDocument();
    expect(screen.queryByText('Henry Wilson')).not.toBeInTheDocument();
  });

  it('shows "Show X more participants" button when more than 5 participants', () => {
    render(<ParticipantsList participants={mockParticipants} />);

    expect(
      screen.getByRole('button', {name: 'Show 3 more participants'})
    ).toBeInTheDocument();
  });

  it('expands to show all participants when button is clicked', async () => {
    const user = userEvent.setup();
    render(<ParticipantsList participants={mockParticipants} />);

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
    render(<ParticipantsList participants={mockParticipants} />);

    await user.click(screen.getByRole('button', {name: 'Show 3 more participants'}));
    await user.click(screen.getByRole('button', {name: 'Show fewer participants'}));

    expect(screen.queryByText('Frank Garcia')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', {name: 'Show 3 more participants'})
    ).toBeInTheDocument();
  });

  it('displays participant roles for non-Participant roles', () => {
    render(<ParticipantsList participants={mockParticipants.slice(0, 3)} />);

    expect(screen.getByText('Captain')).toBeInTheDocument();
    expect(screen.getByText('Reporter')).toBeInTheDocument();
    expect(screen.queryByText('Participant')).not.toBeInTheDocument();
  });
});
