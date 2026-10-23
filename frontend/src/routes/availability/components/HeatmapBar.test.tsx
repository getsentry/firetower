import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router';
import {render, screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';

import {HeatmapBar} from './HeatmapBar';

function renderHeatmap(availability: number[]) {
  const route = createRootRoute({
    component: () => (
      <HeatmapBar
        blocks={availability.map(value => ({
          availability: value,
          periodStart: '2026-09-01',
          periodEnd: '2026-09-30',
          regionName: 'US East',
        }))}
      />
    ),
  });
  const router = createRouter({
    routeTree: route,
    history: createMemoryHistory({initialEntries: ['/']}),
  });
  return render(<RouterProvider router={router} />);
}

describe('HeatmapBar', () => {
  it('links downtime cells to matching incident filters', async () => {
    renderHeatmap([100, 99.87, 99.1]);

    expect(await screen.findByText('100.00%')).toBeInTheDocument();
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveTextContent('99.87%');
    expect(links[1]).toHaveTextContent('99.10%');
    const url = new URL(links[0].getAttribute('href')!, 'http://localhost');
    expect(url.pathname).toBe('/');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      affected_region: '["US East"]',
      created_after: '2026-09-01',
      created_before: '2026-09-30',
      service_tier: '["T0"]',
      impact_type: '["availability"]',
      status: '["Any"]',
    });
  });

  it('keeps near-perfect availability below 100 and full uptime unlinked', async () => {
    renderHeatmap([99.999, 100, 101]);

    expect(await screen.findByRole('link', {name: '99.99%'})).toBeInTheDocument();
    expect(screen.getAllByText('100.00%')).toHaveLength(2);
    expect(screen.getAllByRole('link')).toHaveLength(1);
  });
});
