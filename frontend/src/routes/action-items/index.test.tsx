import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {createMemoryHistory, createRouter, RouterProvider} from '@tanstack/react-router';
import {render, screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, describe, expect, it, vi} from 'vitest';

import {routeTree} from '../../routeTree.gen';

import {
  actionItemDashboardQueryOptions,
  DashboardSchema,
  DashboardSearchSchema,
  type DashboardData,
  type DashboardSearch,
} from './queries/actionItemDashboardQueryOptions';

const {mockApiGet} = vi.hoisted(() => ({mockApiGet: vi.fn()}));
vi.mock('../../api', () => ({Api: {get: mockApiGet}}));

const ENGINEERING_TEAM = '11111111-1111-4111-8111-111111111111';
const INFRASTRUCTURE_TEAM = '22222222-2222-4222-8222-222222222222';

const mockData: DashboardData = {
  generated_at: '2026-11-17T12:00:00+00:00',
  stalled_days: 14,
  due_soon_days: 3,
  summary: {
    open: 12,
    in_progress: 4,
    todo: 8,
    done: 10,
    canceled: 2,
    high_priority_open: 5,
    overdue: 3,
    due_soon: 1,
    stalled: 2,
    unassigned: 1,
    no_priority: 1,
    attention: 6,
    created_30d: 7,
    completed_30d: 8,
    median_completion_days: 9.5,
    on_time_percent: 75,
    on_time_sample: 4,
    unknown_activity: 0,
    unknown_team: 0,
    unknown_completion: 0,
  },
  weeks: Array.from({length: 8}, (_, index) => ({
    start: `2026-10-${String(index + 1).padStart(2, '0')}`,
    created: index,
    completed: index + 1,
  })),
  aging: [
    {label: '0–7 days', count: 4, overdue: 0},
    {label: '8–14 days', count: 3, overdue: 0},
    {label: '15–30 days', count: 2, overdue: 1},
    {label: '31–60 days', count: 2, overdue: 1},
    {label: '61+ days', count: 1, overdue: 1},
  ],
  teams: [
    {
      id: ENGINEERING_TEAM,
      key: 'ENG',
      name: 'Engineering',
      open: 7,
      overdue: 3,
      stalled: 2,
    },
    {
      id: INFRASTRUCTURE_TEAM,
      key: 'INFRA',
      name: 'Infrastructure',
      open: 5,
      overdue: 0,
      stalled: 0,
    },
  ],
  freshness: {
    linked_incidents: 5,
    unlinked_incidents: 0,
    unsynced_incidents: 0,
    stale_incidents: 0,
    oldest_sync_at: '2026-11-17T11:00:00Z',
  },
  queue: {
    count: 12,
    page: 1,
    pages: 2,
    results: [
      {
        id: 1,
        title: 'Add connection pool alerts',
        linear_identifier: 'ENG-123',
        status: 'Todo',
        priority: 2,
        linear_team_id: ENGINEERING_TEAM,
        linear_team_key: 'ENG',
        linear_team_name: 'Engineering',
        url: 'https://linear.app/issue/ENG-123',
        slo_deadline: '2026-11-14T12:00:00Z',
        incident_id: 'INC-2345',
        incident_title: 'Database outage',
        incident_severity: 'P1',
        created_at: '2026-10-31T12:00:00Z',
        linear_updated_at: '2026-11-01T12:00:00Z',
        age_days: 17,
        idle_days: 16,
        flags: ['overdue', 'stalled'],
      },
      {
        id: 2,
        title: 'Document the rollback',
        linear_identifier: 'ENG-124',
        status: 'In Progress',
        priority: 0,
        linear_team_id: INFRASTRUCTURE_TEAM,
        linear_team_key: 'INFRA',
        linear_team_name: 'Infrastructure',
        url: 'https://linear.app/issue/ENG-124',
        slo_deadline: null,
        incident_id: 'INC-2346',
        incident_title: 'Release outage',
        incident_severity: 'P2',
        created_at: '2026-11-16T12:00:00Z',
        linear_updated_at: null,
        age_days: 1,
        idle_days: null,
        flags: ['unassigned', 'no_priority'],
      },
    ],
  },
};

let queryClient: QueryClient;

function setupMocks(data = mockData) {
  mockApiGet.mockImplementation(
    ({path, query}: {path: string; query?: DashboardSearch}) => {
      if (path === '/ui/users/me/')
        return Promise.resolve({name: 'Reader', avatar_url: null});
      if (path === '/ui/action-items/') {
        return Promise.resolve(
          DashboardSchema.parse({...data, queue: {...data.queue, page: query?.page ?? 1}})
        );
      }
      return Promise.reject(new Error('Unexpected request'));
    }
  );
}

async function renderRoute(path = '/action-items') {
  const router = createRouter({
    routeTree,
    context: {queryClient},
    history: createMemoryHistory({initialEntries: [path]}),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
  return router;
}

beforeEach(() => {
  queryClient = new QueryClient({defaultOptions: {queries: {retry: false}}});
  mockApiGet.mockReset();
  sessionStorage.clear();
  setupMocks();
});

describe('Action item dashboard', () => {
  it('is a top-level tab alongside Availability and renders the complete overview', async () => {
    await renderRoute();
    expect(
      await screen.findByRole('heading', {name: 'Action items'})
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', {name: 'Availability'})).toBeInTheDocument();
    expect(within(nav).getByRole('link', {name: 'Action Items'})).toHaveAttribute(
      'href',
      '/action-items'
    );
    expect(screen.queryByText('All Incidents')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Open follow-ups 12/})).toBeInTheDocument();
    expect(screen.getByRole('heading', {name: 'Are we keeping up?'})).toBeInTheDocument();
    expect(screen.getAllByRole('img', {name: /Week of/})).toHaveLength(8);
    expect(
      screen.getByRole('heading', {name: 'How old is the backlog?'})
    ).toBeInTheDocument();
    expect(screen.getByText('9.5d')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
  });

  it('links directly to Linear and incident details and explains risk signals', async () => {
    await renderRoute();
    expect(
      screen.getByRole('link', {name: 'Add connection pool alerts'})
    ).toHaveAttribute('href', 'https://linear.app/issue/ENG-123');
    expect(screen.getByRole('link', {name: 'INC-2345'})).toHaveAttribute(
      'href',
      '/INC-2345'
    );
    expect(screen.getByText('3d overdue')).toBeInTheDocument();
    expect(screen.getByText('16d idle')).toBeInTheDocument();
    expect(screen.getByText('Activity unknown')).toBeInTheDocument();
  });

  it('drills metrics into the queue and clears unrelated queue filters', async () => {
    const user = userEvent.setup();
    const router = await renderRoute(
      `/action-items?severity=P1&page=2&team=${ENGINEERING_TEAM}&q=alerts`
    );
    await user.click(screen.getByRole('button', {name: /^Overdue SLOs 3/}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({severity: 'P1', view: 'overdue'})
    );
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/action-items/',
        query: {severity: 'P1', view: 'overdue'},
      })
    );
  });

  it('preserves severity while applying view, team, and search, resetting the page', async () => {
    const user = userEvent.setup();
    const router = await renderRoute('/action-items?severity=P1&page=2');
    await user.selectOptions(
      screen.getByRole('combobox', {name: 'Queue view'}),
      'stalled'
    );
    await user.selectOptions(
      screen.getByRole('combobox', {name: 'Queue team'}),
      INFRASTRUCTURE_TEAM
    );
    await user.type(screen.getByRole('searchbox'), 'rollback');
    await user.click(screen.getByRole('button', {name: 'Search', exact: true}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        severity: 'P1',
        view: 'stalled',
        team: INFRASTRUCTURE_TEAM,
        q: 'rollback',
      })
    );
    await user.click(screen.getByRole('button', {name: 'Clear filters'}));
    await waitFor(() => expect(router.state.location.search).toEqual({severity: 'P1'}));
  });

  it('drills team breakdowns into that team’s open work', async () => {
    const user = userEvent.setup();
    const router = await renderRoute('/action-items?q=old&page=2');
    await user.click(screen.getByRole('button', {name: /^Engineering/}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({team: ENGINEERING_TEAM, view: 'open'})
    );
  });

  it('changing severity resets queue filters and scopes the API request', async () => {
    const user = userEvent.setup();
    const router = await renderRoute(
      `/action-items?view=overdue&team=${ENGINEERING_TEAM}&page=2`
    );
    const selector = screen.getByRole('group', {name: 'Incident severity'});
    await user.click(within(selector).getByRole('button', {name: 'All severities'}));
    await user.click(screen.getByRole('option', {name: 'P2'}));
    await waitFor(() => expect(router.state.location.search).toEqual({severity: 'P2'}));
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({path: '/ui/action-items/', query: {severity: 'P2'}})
    );
  });

  it('can clear severity with the existing pill selector', async () => {
    const user = userEvent.setup();
    const router = await renderRoute('/action-items?severity=P1');
    const selector = screen.getByRole('group', {name: 'Incident severity'});
    await user.click(within(selector).getByRole('button', {name: 'P1'}));
    await user.click(screen.getByRole('option', {name: 'All severities'}));
    await waitFor(() => expect(router.state.location.search).toEqual({}));
  });

  it('does not expose individual rankings, owner filters, or the tagline', async () => {
    await renderRoute();
    expect(screen.queryByRole('combobox', {name: 'Queue owner'})).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', {name: 'Queue team'})).toBeInTheDocument();
    expect(screen.getByRole('columnheader', {name: 'Linear team'})).toBeInTheDocument();
    expect(screen.queryByText(/Learn from incidents/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Owners ranked/)).not.toBeInTheDocument();
  });

  it('explains priority-based SLOs rather than Linear due dates', async () => {
    const user = userEvent.setup();
    await renderRoute();
    await user.click(screen.getByText('How to read this dashboard'));
    expect(screen.getByText(/not Linear's explicit due date/)).toBeVisible();
    expect(screen.getByText(/Low and unset priority have no SLO target/)).toBeVisible();
    expect(screen.getByText('Completed within SLO')).toBeInTheDocument();
  });

  it('shows unsynced team metadata without attributing it to an individual', async () => {
    setupMocks({
      ...mockData,
      summary: {...mockData.summary, unknown_team: 1},
      teams: [
        ...mockData.teams,
        {
          id: 'unknown',
          key: '',
          name: 'Team not synced',
          open: 1,
          overdue: 0,
          stalled: 0,
        },
      ],
    });
    await renderRoute();
    expect(
      screen.getByText(/1 open follow-ups have no Linear team metadata yet/)
    ).toBeInTheDocument();
    expect(screen.getByRole('option', {name: 'Team not synced (1)'})).toBeInTheDocument();
  });

  it('paginates without losing scope or queue filters', async () => {
    const user = userEvent.setup();
    const router = await renderRoute('/action-items?severity=P1&view=open');
    expect(screen.getByRole('button', {name: 'Previous'})).toBeDisabled();
    await user.click(screen.getByRole('button', {name: 'Next', exact: true}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        severity: 'P1',
        view: 'open',
        page: 2,
      })
    );
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Next', exact: true})).toBeDisabled();
  });

  it('refreshes cached data without issuing a mutation', async () => {
    const user = userEvent.setup();
    await renderRoute();
    const before = mockApiGet.mock.calls.filter(
      ([args]) => args.path === '/ui/action-items/'
    ).length;
    await user.click(screen.getByRole('button', {name: 'Refresh dashboard'}));
    await waitFor(() =>
      expect(
        mockApiGet.mock.calls.filter(([args]) => args.path === '/ui/action-items/')
      ).toHaveLength(before + 1)
    );
  });

  it('warns when data is incomplete instead of implying stalled counts are complete', async () => {
    setupMocks({
      ...mockData,
      summary: {...mockData.summary, unknown_activity: 2},
      freshness: {...mockData.freshness, unsynced_incidents: 1, stale_incidents: 3},
    });
    await renderRoute();
    expect(
      screen.getByText(
        /1 linked incidents have never synced, 3 have not synced in 24h, and 2 open follow-ups/
      )
    ).toBeInTheDocument();
  });

  it('handles an empty report without showing NaN, a fake completion rate, or pagination', async () => {
    setupMocks({
      ...mockData,
      summary: {
        ...mockData.summary,
        open: 0,
        done: 0,
        canceled: 0,
        median_completion_days: null,
        on_time_percent: null,
      },
      teams: [],
      queue: {count: 0, page: 1, pages: 1, results: []},
    });
    await renderRoute();
    expect(
      screen.getByRole('heading', {name: 'No synced follow-ups yet'})
    ).toBeInTheDocument();
    expect(screen.getByText('No open follow-ups in this scope.')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(2);
    expect(screen.getByRole('button', {name: 'Next', exact: true})).toBeDisabled();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it('retains the snapshot and shows a warning on refresh failure', async () => {
    const user = userEvent.setup();
    await renderRoute();
    mockApiGet.mockRejectedValue(new Error('Network failure'));
    await user.click(screen.getByRole('button', {name: 'Refresh dashboard'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Refresh failed');
    expect(
      screen.getByRole('link', {name: 'Add connection pool alerts'})
    ).toBeInTheDocument();
  });

  it('has a recoverable route-level error state', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      mockApiGet.mockRejectedValue(new Error('Network failure'));
      await renderRoute();
      expect(
        await screen.findByRole('heading', {name: 'Unable to load action items'})
      ).toBeInTheDocument();
      expect(screen.getByRole('button', {name: 'Try again'})).toBeInTheDocument();
    } finally {
      log.mockRestore();
    }
  });
});

describe('Dashboard contracts', () => {
  it('validates the response and normalizes malformed URL search parameters', () => {
    expect(DashboardSchema.parse(mockData)).toEqual(mockData);
    expect(
      DashboardSearchSchema.parse({
        page: -3,
        view: 'bad',
        severity: 'P9',
        team: 'bad',
        q: 'x'.repeat(201),
      })
    ).toEqual({});
    expect(DashboardSearchSchema.parse({page: 2, view: 'open', q: '  alerts  '})).toEqual(
      {page: 2, view: 'open', q: 'alerts'}
    );
  });

  it('drops individual identity fields from dashboard rows', () => {
    const withIdentity = {
      ...mockData,
      queue: {
        ...mockData.queue,
        results: [
          {
            ...mockData.queue.results[0],
            assignee_name: 'Not a public ranking',
            assignee_id: 42,
            assignee_avatar_url: 'https://example.com/avatar.png',
          },
        ],
      },
    };
    const row = DashboardSchema.parse(withIdentity).queue.results[0];
    expect(row).not.toHaveProperty('assignee_name');
    expect(row).not.toHaveProperty('assignee_id');
    expect(row).not.toHaveProperty('assignee_avatar_url');
  });

  it('passes scope, queue filters, and abort signal through the shared API client', async () => {
    const search = {severity: 'P1', view: 'overdue', page: 2} as const;
    await queryClient.fetchQuery(actionItemDashboardQueryOptions(search));
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/action-items/',
        query: search,
        signal: expect.any(AbortSignal),
        responseSchema: DashboardSchema,
      })
    );
  });
});
