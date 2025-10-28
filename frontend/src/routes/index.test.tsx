import React from 'react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createMemoryHistory, createRouter, RouterProvider} from '@tanstack/react-router';
import {render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, describe, expect, it, vi} from 'bun:test';

import {routeTree} from '../routeTree.gen';

import type {PaginatedIncidents} from './queries/incidentsQueryOptions';

const mockApiGet = vi.fn();
vi.mock('../api', () => ({
  Api: {
    get: mockApiGet,
  },
}));

const mockIncidents: PaginatedIncidents = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 'INC-1247',
      title: 'Database Connection Pool Exhausted',
      description:
        'Users experiencing 500 errors when trying to access their dashboard. Database connection pool appears to be exhausted, causing new requests to timeout.',
      status: 'Active',
      severity: 'P1',
      created_at: '2024-08-27T18:14:00Z',
      is_private: false,
    },
    {
      id: 'INC-1246',
      title: 'SSL Certificate Renewal Failed',
      description:
        'Automated SSL certificate renewal process failed for api.example.com. Manual intervention required to restore HTTPS access.',
      status: 'Mitigated',
      severity: 'P2',
      created_at: '2024-08-27T15:32:00Z',
      is_private: true,
    },
  ],
};

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function createTestRouter(initialPath = '/') {
  return createRouter({
    routeTree,
    context: {
      queryClient,
    },
    history: createMemoryHistory({
      initialEntries: [initialPath],
    }),
  });
}

const renderRoute = (initialPath = '/') => {
  const router = createTestRouter(initialPath);
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
};

describe('IncidentCard (via Index Route)', () => {
  beforeEach(() => {
    // Reset query client cache and mock API response
    queryClient.clear();
    mockApiGet.mockResolvedValue(mockIncidents);
  });

  it('renders incident cards on the index route', async () => {
    renderRoute();

    expect(await screen.findByText('INC-1247')).toBeInTheDocument();
    expect(
      await screen.findByText('Database Connection Pool Exhausted')
    ).toBeInTheDocument();
    expect(await screen.findByText(/Users experiencing 500 errors/)).toBeInTheDocument();
  });

  it('renders severity and status pills for incidents', async () => {
    renderRoute();

    const card1 = await screen.findByTestId('incident-card-INC-1247');
    const card2 = screen.getByTestId('incident-card-INC-1246');

    expect(within(card1).getByText('P1')).toBeInTheDocument();
    expect(within(card1).getByText('Active')).toBeInTheDocument();

    expect(within(card2).getByText('P2')).toBeInTheDocument();
    expect(within(card2).getByText('Mitigated')).toBeInTheDocument();
  });

  it('renders formatted dates for incidents', async () => {
    renderRoute();

    expect(await screen.findAllByText(/Aug 27, 2024/)).toHaveLength(2);
    expect(await screen.findAllByText(/Opened/)).toHaveLength(2);
  });

  it('shows private pill for private incidents', async () => {
    renderRoute();

    const card2 = await screen.findByTestId('incident-card-INC-1246');
    expect(within(card2).getByText('Private')).toBeInTheDocument();
  });

  it('renders incident cards as clickable links', async () => {
    renderRoute();

    await screen.findByText('INC-1247');

    const linkElements = await screen.findAllByRole('link');
    const incidentLinks = linkElements.filter(link =>
      link.getAttribute('href')?.startsWith('/INC-')
    );

    expect(incidentLinks).toHaveLength(2);
    expect(incidentLinks[0]).toHaveAttribute('href', '/INC-1247');
    expect(incidentLinks[1]).toHaveAttribute('href', '/INC-1246');
  });

  it('calls the incidents API with correct parameters', async () => {
    renderRoute();

    await screen.findByText('INC-1247');

    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/incidents/',
        query: {status: ['Active', 'Mitigated'], page: 1},
      })
    );
  });
});

describe('StatusFilter', () => {
  beforeEach(() => {
    queryClient.clear();
    mockApiGet.mockResolvedValue(mockIncidents);
  });

  it('renders all three filter buttons', async () => {
    renderRoute();

    expect(await screen.findByTestId('filter-active')).toBeInTheDocument();
    expect(await screen.findByTestId('filter-review')).toBeInTheDocument();
    expect(await screen.findByTestId('filter-closed')).toBeInTheDocument();
  });

  it('shows Active filter as active by default', async () => {
    renderRoute();

    const activeButton = await screen.findByTestId('filter-active');
    expect(activeButton).toHaveAttribute('aria-selected', 'true');
  });

  it('changes filter when clicking In Review button', async () => {
    const user = userEvent.setup();
    renderRoute();

    await screen.findByText('INC-1247');
    mockApiGet.mockClear();

    const reviewButton = await screen.findByTestId('filter-review');
    await user.click(reviewButton);

    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/incidents/',
        query: {status: ['Postmortem', 'Actions Pending'], page: 1},
      })
    );
  });

  it('changes filter when clicking Closed button', async () => {
    const user = userEvent.setup();
    renderRoute();

    await screen.findByText('INC-1247');
    mockApiGet.mockClear();

    const closedButton = await screen.findByTestId('filter-closed');
    await user.click(closedButton);

    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/incidents/',
        query: {status: ['Done'], page: 1},
      })
    );
  });

  it('updates active state when filter changes', async () => {
    const user = userEvent.setup();
    renderRoute();

    await screen.findByText('INC-1247');

    const reviewButton = await screen.findByTestId('filter-review');
    await user.click(reviewButton);

    expect(reviewButton).toHaveAttribute('aria-selected', 'true');
  });

  it('shows no filter as selected when URL params do not match any filter group', async () => {
    renderRoute('/?status=%5B%22Active%22%5D');

    await screen.findByTestId('filter-active');

    const activeButton = screen.getByTestId('filter-active');
    const reviewButton = screen.getByTestId('filter-review');
    const closedButton = screen.getByTestId('filter-closed');

    expect(activeButton).toHaveAttribute('aria-selected', 'false');
    expect(reviewButton).toHaveAttribute('aria-selected', 'false');
    expect(closedButton).toHaveAttribute('aria-selected', 'false');
  });
});

describe('Route States', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('shows spinner in pending state with filters visible', async () => {
    mockApiGet.mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve(mockIncidents), 100))
    );

    const router = createRouter({
      routeTree,
      context: {
        queryClient,
      },
      history: createMemoryHistory({
        initialEntries: ['/'],
      }),
      defaultPendingMs: 0, // Show pending state immediately
    });

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    );

    // The spinner should appear while loading
    expect(await screen.findByTestId('spinner')).toBeInTheDocument();

    // Filters should still be visible during loading
    expect(screen.getByTestId('filter-active')).toBeInTheDocument();
    expect(screen.getByTestId('filter-review')).toBeInTheDocument();
    expect(screen.getByTestId('filter-closed')).toBeInTheDocument();

    // Wait for the data to load
    await screen.findByText('INC-1247');
  });

  it('shows error message with filters visible when API fails', async () => {
    mockApiGet.mockRejectedValue(new Error('API Error'));

    renderRoute();

    expect(
      await screen.findByText('Something went wrong fetching incidents.')
    ).toBeInTheDocument();
    expect(screen.getByTestId('filter-active')).toBeInTheDocument();
    expect(screen.getByTestId('filter-review')).toBeInTheDocument();
    expect(screen.getByTestId('filter-closed')).toBeInTheDocument();
  });
});
