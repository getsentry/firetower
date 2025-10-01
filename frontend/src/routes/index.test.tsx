import React from 'react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createMemoryHistory, createRouter, RouterProvider} from '@tanstack/react-router';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, describe, expect, it, vi} from 'bun:test';

import {routeTree} from '../routeTree.gen';

import type {IncidentList} from './queries/incidentsQueryOptions';

const mockApiGet = vi.fn();
vi.mock('../api', () => ({
  Api: {
    get: mockApiGet,
  },
}));

const mockIncidents: IncidentList = [
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
];

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

    expect(await screen.findByText('P1')).toBeInTheDocument();
    expect(await screen.findByText('P2')).toBeInTheDocument();
    expect(await screen.findByText('Mitigated')).toBeInTheDocument();

    const activeElements = await screen.findAllByText('Active');
    expect(activeElements.length).toBeGreaterThan(0);
  });

  it('renders formatted dates for incidents', async () => {
    renderRoute();

    expect(await screen.findAllByText(/Aug 27, 2024/)).toHaveLength(2);
    expect(await screen.findAllByText(/Opened/)).toHaveLength(2);
  });

  it('shows private pill for private incidents', async () => {
    renderRoute();

    expect(await screen.findByText('Private')).toBeInTheDocument();
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
        query: {status: ['Active', 'Mitigated']},
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
        query: {status: ['Postmortem', 'Actions Pending']},
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
        query: {status: ['Done']},
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
