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
  TIME_RANGE_OPTIONS,
  type DashboardData,
  type DashboardSearch,
} from './queries/actionItemDashboardQueryOptions';

const {mockApiGet} = vi.hoisted(() => ({mockApiGet: vi.fn()}));
vi.mock('../../api', () => ({Api: {get: mockApiGet}}));

const ENGINEERING_TEAM = '11111111-1111-4111-8111-111111111111';
const INFRASTRUCTURE_TEAM = '22222222-2222-4222-8222-222222222222';

const mockData: DashboardData = {
  generated_at: '2026-11-17T12:00:00+00:00',
  time_range: {
    key: 'all',
    label: 'All time',
    start: null,
    end: '2026-11-17T12:00:00+00:00',
  },
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
    created_count: 24,
    completed_count: 10,
    median_completion_days: 9.5,
    on_time_percent: 75,
    on_time_sample: 4,
    unknown_activity: 0,
    unknown_team: 0,
    unknown_completion: 0,
  },
  trend: {
    interval: 'Monthly',
    buckets: Array.from({length: 8}, (_, index) => ({
      start: new Date(Date.UTC(2026, index + 3, 1)).toISOString(),
      end: new Date(Date.UTC(2026, index + 4, 1)).toISOString(),
      label: new Date(Date.UTC(2026, index + 3, 1)).toLocaleDateString('en-US', {
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      }),
      created: [2, 4, 3, 2, 5, 4, 2, 2][index],
      completed: [0, 1, 1, 1, 2, 2, 1, 2][index],
    })),
  },
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
      completed: 4,
      canceled: 1,
      total: 12,
      completion_rate: 36.4,
      open: 7,
      overdue: 3,
      stalled: 2,
    },
    {
      id: INFRASTRUCTURE_TEAM,
      key: 'INFRA',
      name: 'Infrastructure',
      completed: 6,
      canceled: 1,
      total: 12,
      completion_rate: 54.5,
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
        deadline_source: 'priority_slo',
        due_date: null,
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
        deadline_source: null,
        due_date: null,
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

function setupMocks(data = mockData, scopedData?: DashboardData) {
  mockApiGet.mockImplementation(
    ({path, query}: {path: string; query?: DashboardSearch}) => {
      if (path === '/ui/users/me/')
        return Promise.resolve({name: 'Reader', avatar_url: null});
      if (path === '/ui/action-items/') {
        const key = query?.time_range ?? 'all';
        const starts = {
          '7d': '2026-11-10',
          '14d': '2026-11-03',
          '1m': '2026-10-17',
          '3m': '2026-08-17',
          '6m': '2026-05-17',
          '9m': '2026-02-17',
          '12m': '2025-11-17',
        };
        const source = key !== 'all' && scopedData ? scopedData : data;
        const time_range = {
          key,
          label:
            key === 'all'
              ? 'All time'
              : TIME_RANGE_OPTIONS.find(option => option.value === key)!.description,
          start: key === 'all' ? null : starts[key] + 'T12:00:00+00:00',
          end: data.generated_at,
        };
        return Promise.resolve(
          DashboardSchema.parse({
            ...source,
            time_range,
            queue: {...source.queue, page: query?.page ?? 1},
          })
        );
      }
      return Promise.reject(new Error('Unexpected request'));
    }
  );
}

async function chooseOption(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  option: string | RegExp
) {
  await user.click(screen.getByRole('combobox', {name: label}));
  await user.click(await screen.findByRole('option', {name: option}));
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
    expect(
      screen.getByText(
        'The health of our incident follow-ups, not just our incidents. ' +
          'Note that this page is very much vibe coded to get something up here quickly. ' +
          "Feel free to contribute to this page if there's something you want to see."
      )
    ).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    expect(
      within(nav)
        .getAllByRole('link')
        .map(link => link.textContent?.trim())
    ).toEqual(['Incidents', 'Action Items', 'Availability']);
    expect(within(nav).getByRole('link', {name: 'Availability'})).toBeInTheDocument();
    expect(within(nav).getByRole('link', {name: 'Action Items'})).toHaveAttribute(
      'href',
      '/action-items'
    );
    expect(screen.queryByText('All Incidents')).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: /Open follow-ups 12/})).toBeInTheDocument();
    expect(screen.getByRole('heading', {name: 'Are we keeping up?'})).toBeInTheDocument();
    expect(screen.getAllByRole('img', {name: /created,.*completed/})).toHaveLength(8);
    expect(screen.getByRole('combobox', {name: 'Time range'})).toHaveTextContent(
      'All time'
    );
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
    await user.click(screen.getByRole('button', {name: /^Overdue 3/}));
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
    await chooseOption(user, 'Queue view', /^Stalled/);
    await chooseOption(user, 'Queue team', /^Infrastructure/);
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
    await user.click(within(selector).getByRole('button', {name: 'All', exact: true}));
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
    await user.click(screen.getByRole('option', {name: 'All', exact: true}));
    await waitFor(() => expect(router.state.location.search).toEqual({}));
  });

  it('does not expose individual rankings, owner filters, or the tagline', async () => {
    await renderRoute();
    expect(screen.queryByRole('combobox', {name: 'Queue owner'})).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', {name: 'Queue team'})).toBeInTheDocument();
    expect(screen.getByRole('columnheader', {name: 'Linear team'})).toBeInTheDocument();
    expect(screen.queryByText(/Learn from incidents/)).not.toBeInTheDocument();
    expect(screen.queryByText('All severities')).not.toBeInTheDocument();
    expect(
      within(screen.getByRole('group', {name: 'Incident severity'})).getByRole('button', {
        name: 'All',
        exact: true,
      })
    ).toBeInTheDocument();
    expect(screen.queryByText(/Owners ranked/)).not.toBeInTheDocument();
  });

  it('explains Linear deadline precedence and sync timing', async () => {
    const user = userEvent.setup();
    await renderRoute();
    await user.click(screen.getByText('How to read this dashboard'));
    expect(screen.getByText(/explicit Linear due date first/)).toBeVisible();
    expect(screen.getByText(/Clearing a due date falls back/)).toBeVisible();
    expect(screen.getByText(/end of that date in UTC/)).toBeVisible();
    expect(screen.getByText('Completed on time')).toBeInTheDocument();
  });

  it.each([
    {source: 'linear_due_date', label: 'Linear due date', date: '2026-11-14'},
    {source: 'linear_sla', label: 'Linear SLA', date: null},
    {source: 'priority_slo', label: 'Priority SLO', date: null},
  ] as const)(
    'shows the actual deadline source: $source',
    async ({source, label, date}) => {
      setupMocks({
        ...mockData,
        queue: {
          ...mockData.queue,
          results: [
            {...mockData.queue.results[0], deadline_source: source, due_date: date},
          ],
        },
      });
      await renderRoute();
      expect(screen.getByText(new RegExp('^' + label + ':'))).toBeInTheDocument();
      if (date) expect(screen.getByText(label + ': ' + date)).toBeInTheDocument();
    }
  );

  it('does not call work without a deadline on time', async () => {
    setupMocks({
      ...mockData,
      queue: {
        ...mockData.queue,
        results: [{...mockData.queue.results[1], priority: 4, flags: []}],
      },
    });
    await renderRoute();
    expect(screen.getByText('No deadline')).toBeInTheDocument();
    expect(screen.queryByText('Within deadline')).not.toBeInTheDocument();
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
          completed: 0,
          canceled: 0,
          total: 1,
          completion_rate: 0,
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
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', {name: 'Queue team'}));
    expect(
      await screen.findByRole('option', {name: /^Team not synced/})
    ).toBeInTheDocument();
  });

  it('keeps the delivery sample above the divider and only lists at-risk teams', async () => {
    await renderRoute();
    const card = screen.getByRole('heading', {
      name: 'Delivery · all time',
    }).parentElement!;
    const note = within(card).getByText(/4 completed follow-ups with a deadline/);
    const divider = within(card).getByRole('separator');
    expect(
      note.compareDocumentPosition(divider) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(
      screen.queryByRole('heading', {name: 'Where help is needed'})
    ).not.toBeInTheDocument();
    expect(within(card).getByRole('button', {name: /^Engineering/})).toBeInTheDocument();
    expect(
      within(card).queryByRole('button', {name: /^Infrastructure/})
    ).not.toBeInTheDocument();
  });

  it('provides positive team progress without native selects or extra API requests', async () => {
    const user = userEvent.setup();
    const router = await renderRoute();
    const before = mockApiGet.mock.calls.length;
    expect(screen.getByRole('heading', {name: 'Team progress'})).toBeInTheDocument();
    await chooseOption(user, 'Leaderboard metric', 'Completion rate');
    await chooseOption(user, 'Leaderboard team', /^Infrastructure/);
    expect(router.state.location.search).toEqual({});
    expect(mockApiGet).toHaveBeenCalledTimes(before);
    expect(document.querySelector('main select')).toBeNull();
  });

  it('offers all requested global time ranges and applies scoped data to every panel', async () => {
    const user = userEvent.setup();
    const scoped: DashboardData = {
      ...mockData,
      summary: {
        ...mockData.summary,
        open: 1,
        todo: 0,
        in_progress: 1,
        done: 1,
        canceled: 0,
        high_priority_open: 0,
        overdue: 0,
        due_soon: 0,
        stalled: 0,
        unassigned: 1,
        no_priority: 1,
        attention: 1,
        created_count: 2,
        completed_count: 1,
        median_completion_days: 2,
        on_time_percent: 100,
        on_time_sample: 1,
      },
      trend: {
        interval: 'Daily',
        buckets: [
          {
            start: '2026-11-16T00:00:00Z',
            end: '2026-11-17T00:00:00Z',
            label: 'Nov 16',
            created: 1,
            completed: 0,
          },
          {
            start: '2026-11-17T00:00:00Z',
            end: '2026-11-18T00:00:00Z',
            label: 'Nov 17',
            created: 1,
            completed: 1,
          },
        ],
      },
      aging: mockData.aging.map((bucket, index) => ({
        ...bucket,
        count: index === 0 ? 1 : 0,
        overdue: 0,
      })),
      teams: [
        {
          ...mockData.teams[1],
          open: 1,
          completed: 1,
          overdue: 0,
          stalled: 0,
          canceled: 0,
          total: 2,
          completion_rate: 50,
        },
      ],
      queue: {count: 1, page: 1, pages: 1, results: [mockData.queue.results[1]]},
    };
    setupMocks(mockData, scoped);
    const router = await renderRoute(
      `/action-items?severity=P1&view=overdue&team=${ENGINEERING_TEAM}&page=2&q=alerts`
    );
    await user.click(screen.getByRole('combobox', {name: 'Time range'}));
    for (const option of TIME_RANGE_OPTIONS) {
      expect(
        screen.getByRole('option', {name: new RegExp('^' + option.label)})
      ).toBeInTheDocument();
    }
    await user.click(screen.getByRole('option', {name: /^7d/}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({severity: 'P1', time_range: '7d'})
    );
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/action-items/',
        query: {severity: 'P1', time_range: '7d'},
      })
    );
    expect(screen.getByRole('button', {name: /Open follow-ups 1/})).toBeInTheDocument();
    expect(screen.getByText('Completed · last 7 days')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {name: 'Delivery · last 7 days'})
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Last 7 days · current linked follow-ups/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Older open and overdue work is excluded/)
    ).toBeInTheDocument();
    expect(screen.getAllByRole('img', {name: /created,.*completed/})).toHaveLength(2);
    expect(screen.getAllByRole('rowheader')).toHaveLength(1);
    expect(screen.getByText('1 matching follow-up')).toBeInTheDocument();
    await chooseOption(user, 'Time range', /^All time/);
    await waitFor(() => expect(router.state.location.search).toEqual({severity: 'P1'}));
    expect(screen.getByRole('button', {name: /Open follow-ups 12/})).toBeInTheDocument();
  });

  it('preserves the global range through severity, queue filters, and pagination', async () => {
    const user = userEvent.setup();
    const router = await renderRoute('/action-items?time_range=3m&severity=P1');
    const selector = screen.getByRole('group', {name: 'Incident severity'});
    await user.click(within(selector).getByRole('button', {name: 'P1'}));
    await user.click(screen.getByRole('option', {name: 'P2'}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({severity: 'P2', time_range: '3m'})
    );
    await chooseOption(user, 'Queue view', /^All open/);
    await user.click(screen.getByRole('button', {name: 'Next', exact: true}));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        severity: 'P2',
        time_range: '3m',
        view: 'open',
        page: 2,
      })
    );
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
        time_range: '30d',
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
