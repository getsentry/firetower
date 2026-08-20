import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

import type {TimelineEvent} from '../queries/incidentTimelineQueryOptions';

import {IncidentTimeline} from './IncidentTimeline';

const {mockApiGet} = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
}));

vi.mock('api', () => ({
  Api: {
    get: mockApiGet,
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

function renderTimeline(incidentId = 'INC-123') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {retry: false},
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <IncidentTimeline incidentId={incidentId} />
    </QueryClientProvider>
  );
}

const events: TimelineEvent[] = [
  {
    id: 1,
    source: 'INTERNAL',
    event_type: 'incident_created',
    occurred_at: '2026-08-20T15:00:00Z',
    created_at: '2026-08-20T15:00:01Z',
    actor: {
      email: 'taylor@example.com',
      name: 'Taylor Osler',
      avatar_url: 'https://example.com/taylor.png',
    },
    summary: 'Incident created at severity P1',
    payload: {severity: 'P1'},
    link_url: '',
    external_id: '',
  },
  {
    id: 2,
    source: 'INTERNAL',
    event_type: 'status_changed',
    occurred_at: '2026-08-20T16:30:00Z',
    created_at: '2026-08-20T16:30:01Z',
    actor: null,
    summary: 'Status changed: Active → Mitigated',
    payload: {old: 'Active', new: 'Mitigated'},
    link_url: 'https://status.example.com/incidents/123',
    external_id: '',
  },
];

describe('IncidentTimeline', () => {
  beforeEach(() => {
    mockApiGet.mockReset();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('requests the incident timeline and renders events in API order', async () => {
    mockApiGet.mockResolvedValue(events);

    renderTimeline('INC-456');

    expect(await screen.findByText(events[0].summary)).toBeInTheDocument();
    expect(mockApiGet).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/ui/incidents/INC-456/timeline-events/',
        signal: expect.any(AbortSignal),
      })
    );

    const summaries = screen
      .getAllByRole('listitem')
      .map(item => item.querySelector('p')?.textContent);
    expect(summaries).toEqual([events[0].summary, events[1].summary]);
  });

  it('renders absolute times, an actor, and the source fallback', async () => {
    mockApiGet.mockResolvedValue(events);

    const {container} = renderTimeline();

    expect(await screen.findByText('Taylor Osler')).toBeInTheDocument();
    const avatar = container.querySelector('img[src="https://example.com/taylor.png"]');
    expect(avatar).toBeInTheDocument();
    expect(avatar?.parentElement).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('img', {name: 'Taylor Osler'})).not.toBeInTheDocument();
    expect(screen.getByText('Firetower')).toBeInTheDocument();

    const firstTime = container.querySelector('time');
    expect(firstTime).toHaveAttribute('datetime', events[0].occurred_at);
    expect(firstTime).toHaveTextContent(
      new Date(events[0].occurred_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZoneName: 'short',
      })
    );
  });

  it('renders an optional external source link safely', async () => {
    mockApiGet.mockResolvedValue(events);

    renderTimeline();

    const sourceLink = await screen.findByRole('link', {name: 'View source'});
    expect(sourceLink).toHaveAttribute('href', events[1].link_url);
    expect(sourceLink).toHaveAttribute('target', '_blank');
    expect(sourceLink).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders the empty state without deferred controls', async () => {
    mockApiGet.mockResolvedValue([]);

    renderTimeline();

    expect(await screen.findByText('No timeline events yet.')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByText(/filter/i)).not.toBeInTheDocument();
  });

  it('keeps the heading visible while loading and shows three skeleton rows', () => {
    mockApiGet.mockReturnValue(new Promise(() => {}));

    renderTimeline();

    expect(screen.getByRole('heading', {name: 'Timeline', level: 2})).toBeInTheDocument();
    expect(screen.getByRole('status', {name: 'Loading timeline'})).toBeInTheDocument();
    expect(screen.getAllByTestId('timeline-skeleton-row')).toHaveLength(3);
  });

  it('keeps the heading visible and shows a local alert when loading fails', async () => {
    mockApiGet.mockRejectedValue(new Error('boom'));

    renderTimeline();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Failed to load timeline events. Please try again.'
      );
    });
    expect(screen.getByRole('heading', {name: 'Timeline', level: 2})).toBeInTheDocument();
  });
});
