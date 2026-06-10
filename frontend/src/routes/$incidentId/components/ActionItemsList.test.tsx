import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen, waitFor} from '@testing-library/react';
import {TooltipProvider} from 'components/Tooltip';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

import type {ActionItem} from '../queries/actionItemsQueryOptions';

import {ActionItemsList} from './ActionItemsList';

const {mockApiGet, mockApiPost} = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
  mockApiPost: vi.fn(),
}));

vi.mock('api', () => ({
  Api: {
    get: mockApiGet,
    post: mockApiPost,
    patch: vi.fn(),
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {retry: false},
      mutations: {retry: false},
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{ui}</TooltipProvider>
    </QueryClientProvider>
  );
}

const mockActionItems: ActionItem[] = [
  {
    linear_identifier: 'TEAM-101',
    title: 'Investigate slow query',
    status: 'Todo',
    priority: 2,
    assignee_name: 'Alice Smith',
    assignee_avatar_url: null,
    url: 'https://linear.app/team/issue/TEAM-101',
    slo_deadline: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    linear_identifier: 'TEAM-102',
    title: 'Add monitoring dashboard',
    status: 'In Progress',
    priority: 3,
    assignee_name: null,
    assignee_avatar_url: null,
    url: 'https://linear.app/team/issue/TEAM-102',
    slo_deadline: null,
  },
];

describe('ActionItemsList', () => {
  beforeEach(() => {
    mockApiGet.mockReset();
    mockApiPost.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows empty-state message and sync button when linearUrl is undefined; hides create button', () => {
    renderWithProviders(<ActionItemsList incidentId="INC-1" />);

    expect(
      screen.getByText(/This incident has no linked Linear issue/)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Sync action items'})).toBeInTheDocument();
    expect(
      screen.queryByRole('button', {name: 'Create action item'})
    ).not.toBeInTheDocument();
  });

  it('renders header, sync, and create buttons when linearUrl is set', async () => {
    mockApiGet.mockResolvedValue([]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(
      screen.getByRole('heading', {name: 'Action Items', level: 2})
    ).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Sync action items'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Create action item'})).toBeInTheDocument();
  });

  it('with linearUrl + 0 items: shows "Nothing here yet" while header stays visible', async () => {
    mockApiGet.mockResolvedValue([]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(await screen.findByText('Nothing here yet')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {name: 'Action Items', level: 2})
    ).toBeInTheDocument();
  });

  it('with linearUrl + items: renders each item title and identifier', async () => {
    mockApiGet.mockResolvedValue(mockActionItems);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(await screen.findByText('Investigate slow query')).toBeInTheDocument();
    expect(screen.getByText('TEAM-101')).toBeInTheDocument();
    expect(screen.getByText('Add monitoring dashboard')).toBeInTheDocument();
    expect(screen.getByText('TEAM-102')).toBeInTheDocument();
  });

  it('shows overdue label when slo_deadline is less than a day overdue', async () => {
    const halfDayAgo = new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString();
    mockApiGet.mockResolvedValue([
      {
        ...mockActionItems[0],
        slo_deadline: halfDayAgo,
        status: 'Todo',
      },
    ]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(await screen.findByText('0d overdue')).toBeInTheDocument();
  });

  it('shows overdue label when slo_deadline is more than a day overdue', async () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    mockApiGet.mockResolvedValue([
      {
        ...mockActionItems[0],
        slo_deadline: twoDaysAgo,
        status: 'Todo',
      },
    ]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(await screen.findByText(/overdue/)).toBeInTheDocument();
  });

  it('shows warning-styled days left when slo_deadline is within 3 days', async () => {
    const twoDaysFromNow = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString();
    mockApiGet.mockResolvedValue([
      {
        ...mockActionItems[0],
        slo_deadline: twoDaysFromNow,
        status: 'Todo',
      },
    ]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    expect(await screen.findByText(/\dd left/)).toBeInTheDocument();
  });

  it('does not show slo label for terminal action items', async () => {
    const halfDayAgo = new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString();
    mockApiGet.mockResolvedValue([
      {
        ...mockActionItems[0],
        slo_deadline: halfDayAgo,
        status: 'Done',
      },
    ]);

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    await screen.findByText('Investigate slow query');
    expect(screen.queryByText(/overdue/)).not.toBeInTheDocument();
  });

  it('renders fallback when the action items query fails, with header + sync button still visible', async () => {
    mockApiGet.mockRejectedValue(new Error('boom'));

    renderWithProviders(
      <ActionItemsList
        incidentId="INC-1"
        linearUrl="https://linear.app/team/issue/INC-1"
      />
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          /Failed to load action items. Try refreshing, or come let us know in/
        )
      ).toBeInTheDocument();
    });

    expect(
      screen.getByRole('heading', {name: 'Action Items', level: 2})
    ).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Sync action items'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Create action item'})).toBeInTheDocument();
  });
});
