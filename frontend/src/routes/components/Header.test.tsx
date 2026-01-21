import React from 'react';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createMemoryHistory, createRouter, RouterProvider} from '@tanstack/react-router';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, describe, expect, it, vi} from 'bun:test';

import {routeTree} from '../../routeTree.gen';
import type {IncidentDetail} from '../$incidentId/queries/incidentDetailQueryOptions';
import type {CurrentUser} from '../queries/currentUserQueryOptions';
import type {PaginatedIncidents} from '../queries/incidentsQueryOptions';

const mockApiGet = vi.fn();
vi.mock('../../api', () => ({
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
      service_tier: null,
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
      service_tier: null,
      created_at: '2024-08-27T15:32:00Z',
      is_private: true,
    },
  ],
};

const mockIncidentDetail: IncidentDetail = {
  id: 'INC-1247',
  title: 'Database Connection Pool Exhausted',
  description:
    'Users experiencing 500 errors when trying to access their dashboard. Database connection pool appears to be exhausted, causing new requests to timeout.',
  impact_summary: 'High - affecting 30% of users',
  status: 'Active',
  severity: 'P1',
  service_tier: null,
  created_at: '2024-08-27T18:14:00Z',
  updated_at: '2024-08-27T19:30:00Z',
  is_private: false,
  affected_service_tags: ['Authentication', 'Database'],
  affected_region_tags: [],
  root_cause_tags: ['Connection pool exhaustion', 'Memory leak in connection handler'],
  impact_type_tags: [],
  participants: [
    {
      name: 'John Doe',
      avatar_url: 'https://example.com/avatar.jpg',
      role: 'Captain',
    },
  ],
  external_links: {
    slack: 'https://slack.com/archives/C123456',
  },
  time_started: null,
  time_detected: null,
  time_analyzed: null,
  time_mitigated: null,
  time_recovered: null,
};

const mockCurrentUser: CurrentUser = {
  name: 'Test User',
  avatar_url: null,
};

const STORAGE_KEY = 'firetower_list_search';

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

describe('Header - Root Route (Incident List)', () => {
  beforeEach(() => {
    queryClient.clear();
    sessionStorage.clear();
    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(mockCurrentUser);
      }
      return Promise.reject(new Error('Not found'));
    });
  });

  it('shows centered logo without back button', async () => {
    renderRoute('/');

    expect(await screen.findByText('INC-1247')).toBeInTheDocument();

    expect(screen.getByAltText('Firetower')).toBeInTheDocument();

    expect(screen.queryByText('All Incidents')).not.toBeInTheDocument();
    expect(screen.queryByText('←')).not.toBeInTheDocument();
  });

  it('stores search params in sessionStorage when filtering', async () => {
    const user = userEvent.setup();
    renderRoute('/');

    await screen.findByText('INC-1247');

    const reviewButton = screen.getByTestId('filter-review');
    await user.click(reviewButton);

    const stored = sessionStorage.getItem(STORAGE_KEY);
    expect(stored).not.toBeNull();

    const parsed = JSON.parse(stored!);
    expect(parsed).toEqual({status: ['Postmortem']});
  });

  it('stores empty search params in sessionStorage on initial load', async () => {
    renderRoute('/');

    await screen.findByText('INC-1247');

    const stored = sessionStorage.getItem(STORAGE_KEY);
    expect(stored).not.toBeNull();

    const parsed = JSON.parse(stored!);
    expect(parsed).toEqual({});
  });
});

describe('Header - Incident Detail Route', () => {
  beforeEach(() => {
    queryClient.clear();
    sessionStorage.clear();
    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/incidents/INC-1247/') {
        return Promise.resolve(mockIncidentDetail);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(mockCurrentUser);
      }
      return Promise.reject(new Error('Not found'));
    });
  });

  it('shows back button with centered logo', async () => {
    renderRoute('/INC-1247');

    expect(
      await screen.findByText('Database Connection Pool Exhausted')
    ).toBeInTheDocument();

    expect(screen.getByAltText('Firetower')).toBeInTheDocument();

    expect(screen.getByText('All Incidents')).toBeInTheDocument();
    expect(screen.getByText('←')).toBeInTheDocument();
  });

  it('back button links to root without search params when sessionStorage is empty', async () => {
    renderRoute('/INC-1247');

    await screen.findByText('Database Connection Pool Exhausted');

    const backButton = screen.getByText('All Incidents').closest('a');
    expect(backButton).toHaveAttribute('href', '/');
  });

  it('back button preserves search params from sessionStorage', async () => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({status: ['Postmortem']}));

    renderRoute('/INC-1247');

    await screen.findByText('Database Connection Pool Exhausted');

    const backButton = screen.getByText('All Incidents').closest('a');
    const href = backButton?.getAttribute('href');

    expect(href).toContain('status');
    expect(href).toContain('Postmortem');
  });

  it('navigates back to list with preserved filters', async () => {
    const user = userEvent.setup();
    renderRoute('/');

    await screen.findByText('INC-1247');

    const reviewButton = screen.getByTestId('filter-review');
    await user.click(reviewButton);

    expect(reviewButton).toHaveAttribute('aria-selected', 'true');

    const incidentLink = screen.getByText('INC-1247').closest('a');
    expect(incidentLink).not.toBeNull();
    await user.click(incidentLink!);

    await screen.findByText('Database Connection Pool Exhausted');

    const backButton = screen.getByText('All Incidents').closest('a');
    expect(backButton).not.toBeNull();
    await user.click(backButton!);

    await screen.findByText('INC-1247');

    const reviewButtonAfterNav = screen.getByTestId('filter-review');
    expect(reviewButtonAfterNav).toHaveAttribute('aria-selected', 'true');
  });
});

describe('Header - User Avatar', () => {
  beforeEach(() => {
    queryClient.clear();
    sessionStorage.clear();
    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(mockCurrentUser);
      }
      return Promise.reject(new Error('Not found'));
    });
  });

  it('displays user avatar with initials when no avatar_url', async () => {
    renderRoute('/');

    await screen.findByText('INC-1247');

    // Wait for avatar to load (after Suspense resolves)
    expect(await screen.findByText('TU', {}, {timeout: 3000})).toBeInTheDocument();
  });

  it('displays user avatar with image when avatar_url is provided', async () => {
    const userWithAvatar: CurrentUser = {
      name: 'John Doe',
      avatar_url: 'https://example.com/avatar.jpg',
    };

    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(userWithAvatar);
      }
      return Promise.reject(new Error('Not found'));
    });

    renderRoute('/');

    await screen.findByText('INC-1247');

    // Wait for avatar to load (after Suspense resolves)
    const avatar = await screen.findByAltText('John Doe', {}, {timeout: 3000});
    expect(avatar).toBeInTheDocument();
    expect(avatar).toHaveAttribute('src', 'https://example.com/avatar.jpg');
  });

  it('shows avatar on incident detail page', async () => {
    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/incidents/INC-1247/') {
        return Promise.resolve(mockIncidentDetail);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(mockCurrentUser);
      }
      return Promise.reject(new Error('Not found'));
    });

    renderRoute('/INC-1247');

    await screen.findByText('Database Connection Pool Exhausted');

    // Wait for avatar to load (after Suspense resolves)
    expect(await screen.findByText('TU', {}, {timeout: 3000})).toBeInTheDocument();
  });
});

describe('Header - sessionStorage Handling', () => {
  beforeEach(() => {
    queryClient.clear();
    sessionStorage.clear();
    mockApiGet.mockImplementation((args: {path: string}) => {
      if (args.path === '/ui/incidents/') {
        return Promise.resolve(mockIncidents);
      }
      if (args.path === '/ui/incidents/INC-1247/') {
        return Promise.resolve(mockIncidentDetail);
      }
      if (args.path === '/ui/users/me/') {
        return Promise.resolve(mockCurrentUser);
      }
      return Promise.reject(new Error('Not found'));
    });
  });

  it('handles invalid JSON in sessionStorage gracefully', async () => {
    sessionStorage.setItem(STORAGE_KEY, '{invalid json}');

    renderRoute('/INC-1247');

    await screen.findByText('Database Connection Pool Exhausted');

    expect(screen.getByText('All Incidents')).toBeInTheDocument();

    const backButton = screen.getByText('All Incidents').closest('a');
    expect(backButton).toHaveAttribute('href', '/');
  });

  it('handles missing sessionStorage gracefully', async () => {
    renderRoute('/INC-1247');

    await screen.findByText('Database Connection Pool Exhausted');

    expect(screen.getByText('All Incidents')).toBeInTheDocument();

    const backButton = screen.getByText('All Incidents').closest('a');
    expect(backButton).toHaveAttribute('href', '/');
  });

  it('updates sessionStorage when filters change', async () => {
    const user = userEvent.setup();
    renderRoute('/');

    await screen.findByText('INC-1247');

    let stored = sessionStorage.getItem(STORAGE_KEY);
    let parsed = JSON.parse(stored!);
    expect(parsed).toEqual({});

    const reviewButton = screen.getByTestId('filter-review');
    await user.click(reviewButton);

    stored = sessionStorage.getItem(STORAGE_KEY);
    parsed = JSON.parse(stored!);
    expect(parsed).toEqual({status: ['Postmortem']});

    const closedButton = screen.getByTestId('filter-closed');
    await user.click(closedButton);

    stored = sessionStorage.getItem(STORAGE_KEY);
    parsed = JSON.parse(stored!);
    expect(parsed).toEqual({status: ['Done', 'Cancelled']});
  });
});
