import React from 'react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createMemoryHistory, createRouter, RouterProvider} from '@tanstack/react-router';
import {render, screen} from '@testing-library/react';
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

const router = createRouter({
  routeTree,
  context: {
    queryClient,
  },
  history: createMemoryHistory({
    initialEntries: ['/'],
  }),
});

const renderRoute = () =>
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );

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

    expect(mockApiGet).toHaveBeenCalledWith({
      path: '/ui/incidents/',
      query: {status: ['Active', 'Mitigated']},
      signal: expect.any(AbortSignal),
      responseSchema: expect.any(Object),
    });
  });
});
