import {render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it} from 'vitest';

import type {DashboardTeam} from '../queries/actionItemDashboardQueryOptions';

import {TeamLeaderboard} from './TeamLeaderboard';

function team(
  values: Pick<DashboardTeam, 'id' | 'name'> & Partial<DashboardTeam>
): DashboardTeam {
  const completed = values.completed ?? 0;
  const open = values.open ?? 0;
  const canceled = values.canceled ?? 0;
  return {
    key: '',
    open,
    completed,
    canceled,
    overdue: 0,
    stalled: 0,
    total: completed + open + canceled,
    completion_rate:
      completed + open ? Math.round((completed * 1000) / (completed + open)) / 10 : null,
    ...values,
  };
}

const TEAMS = [
  team({id: 'eng', name: 'Engineering', completed: 6, open: 4, overdue: 3}),
  team({id: 'infra', name: 'Infrastructure', completed: 10, open: 20, overdue: 1}),
  team({id: 'closed', name: 'Completed team', completed: 4}),
  team({id: 'canceled', name: 'Canceled team', canceled: 40}),
];

function names() {
  return screen.getAllByRole('rowheader').map(header => header.textContent);
}

async function select(
  user: ReturnType<typeof userEvent.setup>,
  label: string,
  option: string
) {
  await user.click(screen.getByRole('combobox', {name: label}));
  await user.click(await screen.findByRole('option', {name: option}));
}

describe('TeamLeaderboard', () => {
  it('defaults to completions and includes teams with no remaining open work', () => {
    render(<TeamLeaderboard data={{teams: TEAMS}} />);
    expect(names()).toEqual([
      'Infrastructure',
      'Engineering',
      'Completed team',
      'Canceled team',
    ]);
    expect(screen.getByRole('columnheader', {name: 'Completed'})).toHaveAttribute(
      'aria-sort',
      'descending'
    );
    const completed = screen
      .getByRole('rowheader', {name: 'Completed team'})
      .closest('tr')!;
    expect(within(completed).getByText('100%')).toBeInTheDocument();
    expect(TEAMS[0].id).toBe('eng');
  });

  it.each([
    {
      metric: 'Completion rate',
      column: 'Completion rate',
      expected: ['Completed team', 'Engineering', 'Infrastructure', 'Canceled team'],
    },
    {
      metric: 'Total items',
      column: 'Total',
      expected: ['Canceled team', 'Infrastructure', 'Engineering', 'Completed team'],
    },
    {
      metric: 'Overdue items',
      column: 'Overdue',
      expected: ['Engineering', 'Infrastructure', 'Completed team', 'Canceled team'],
    },
    {
      metric: 'Open items',
      column: 'Open',
      expected: ['Infrastructure', 'Engineering', 'Completed team', 'Canceled team'],
    },
  ])('ranks by $metric', async ({metric, column, expected}) => {
    const user = userEvent.setup();
    render(<TeamLeaderboard data={{teams: TEAMS}} />);
    await select(user, 'Leaderboard metric', metric);
    expect(names()).toEqual(expected);
    expect(screen.getByRole('columnheader', {name: column, exact: true})).toHaveAttribute(
      'aria-sort',
      'descending'
    );
    expect(document.querySelectorAll('[aria-sort]')).toHaveLength(1);
  });

  it('filters by team while retaining its scope-wide rank', async () => {
    const user = userEvent.setup();
    render(<TeamLeaderboard data={{teams: TEAMS}} />);
    await select(user, 'Leaderboard team', 'Engineering');
    expect(names()).toEqual(['Engineering']);
    const row = screen.getByRole('rowheader', {name: 'Engineering'}).closest('tr')!;
    expect(within(row).getAllByRole('cell')[0]).toHaveTextContent('2');
    await select(user, 'Leaderboard team', 'All teams');
    expect(names()).toHaveLength(4);
  });

  it('does not treat canceled-only teams as 100% completed', () => {
    render(<TeamLeaderboard data={{teams: TEAMS}} />);
    const row = screen.getByRole('rowheader', {name: 'Canceled team'}).closest('tr')!;
    expect(within(row).getAllByRole('cell').at(-1)).toHaveTextContent('—');
    expect(screen.getByText(/completion rate is completed ÷/)).toBeInTheDocument();
  });

  it('shows unknown team metadata without ranking that combined bucket', async () => {
    const user = userEvent.setup();
    render(
      <TeamLeaderboard
        data={{
          teams: [
            ...TEAMS,
            team({id: 'unknown', name: 'Team not synced', completed: 500}),
          ],
        }}
      />
    );
    expect(names().at(-1)).toBe('Team not synced');
    await select(user, 'Leaderboard team', 'Team not synced');
    const row = screen.getByRole('rowheader', {name: 'Team not synced'}).closest('tr')!;
    expect(within(row).getAllByRole('cell')[0]).toHaveTextContent('—');
  });

  it('bounds the initial table and allows expanding all teams', async () => {
    const user = userEvent.setup();
    const teams = Array.from({length: 12}, (_, index) =>
      team({id: String(index), name: `Team ${index}`, completed: 12 - index})
    );
    render(<TeamLeaderboard data={{teams}} />);
    expect(names()).toHaveLength(8);
    await user.click(screen.getByRole('button', {name: 'Show all 12 teams'}));
    expect(names()).toHaveLength(12);
    await select(user, 'Leaderboard metric', 'Completion rate');
    expect(names()).toHaveLength(8);
  });

  it('has a useful empty state without invalid percentages', () => {
    render(<TeamLeaderboard data={{teams: []}} />);
    expect(
      screen.getByText('No synced team follow-ups in this scope yet.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });
});
