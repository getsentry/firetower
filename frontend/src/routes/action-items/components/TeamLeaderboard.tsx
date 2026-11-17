import {useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {SearchableSelect} from 'components/SearchableSelect';

import {border, content, fontSize, space} from '../../../styles/tokens.stylex';
import type {DashboardData} from '../queries/actionItemDashboardQueryOptions';

import {styles} from './styles';

const METRICS = [
  {value: 'completed', label: 'Completed items'},
  {value: 'completion_rate', label: 'Completion rate'},
  {value: 'total', label: 'Total items'},
  {value: 'open', label: 'Open items'},
  {value: 'overdue', label: 'Overdue items'},
] as const;
type TeamMetric = (typeof METRICS)[number]['value'];
const VISIBLE_TEAMS = 8;

export function TeamLeaderboard({data}: {data: Pick<DashboardData, 'teams'>}) {
  const [metric, setMetric] = useState<TeamMetric>('completed');
  const [teamFilter, setTeamFilter] = useState('');
  const [expanded, setExpanded] = useState(false);
  const activeTeam = data.teams.some(team => team.id === teamFilter) ? teamFilter : '';
  const ranked = [...data.teams]
    .sort(
      (a, b) =>
        Number(a.id === 'unknown') - Number(b.id === 'unknown') ||
        (b[metric] ?? -1) - (a[metric] ?? -1) ||
        b.completed - a.completed ||
        b.total - a.total ||
        a.name.localeCompare(b.name) ||
        a.id.localeCompare(b.id)
    )
    .map((team, index) => ({team, rank: team.id === 'unknown' ? null : index + 1}));
  const filtered = activeTeam ? ranked.filter(row => row.team.id === activeTeam) : ranked;
  const visible = expanded ? filtered : filtered.slice(0, VISIBLE_TEAMS);

  return (
    <Card style={styles.card}>
      <section aria-labelledby="team-progress-heading">
        <div {...stylex.props(styles.cardHeader)}>
          <div>
            <h2 id="team-progress-heading" {...stylex.props(styles.heading)}>
              Team progress
            </h2>
            <p {...stylex.props(styles.muted)}>
              Recognize completed follow-through, and compare team-level progress.
            </p>
          </div>
          <div {...stylex.props(styles.controls)}>
            <span {...stylex.props(styles.muted)}>Rank by</span>
            <SearchableSelect
              label="Leaderboard metric"
              value={metric}
              options={METRICS}
              onChange={value => {
                setMetric(value);
                setExpanded(false);
              }}
            />
            <SearchableSelect
              label="Leaderboard team"
              value={activeTeam}
              options={[
                {value: '', label: 'All teams'},
                ...data.teams.map(team => ({
                  value: team.id,
                  label: team.name,
                  description: team.key || undefined,
                })),
              ]}
              onChange={value => {
                setTeamFilter(value);
                setExpanded(false);
              }}
            />
          </div>
        </div>
        {visible.length ? (
          <div
            role="region"
            aria-label="Team progress table"
            tabIndex={0}
            {...stylex.props(styles.scroll)}
          >
            <table {...stylex.props(tableStyles.table)}>
              <caption {...stylex.props(tableStyles.caption)}>
                All time · current linked follow-ups. Total includes canceled work;
                completion rate is completed ÷ (completed + open). Rankings are among all
                teams in this scope; unsynced team metadata is unranked.
              </caption>
              <thead>
                <tr>
                  <th scope="col" {...stylex.props(tableStyles.heading)}>
                    Rank
                  </th>
                  <th scope="col" {...stylex.props(tableStyles.heading)}>
                    Team
                  </th>
                  <th
                    scope="col"
                    aria-sort={metric === 'completed' ? 'descending' : undefined}
                    {...stylex.props(tableStyles.heading)}
                  >
                    Completed
                  </th>
                  <th
                    scope="col"
                    aria-sort={metric === 'open' ? 'descending' : undefined}
                    {...stylex.props(tableStyles.heading)}
                  >
                    Open
                  </th>
                  <th
                    scope="col"
                    aria-sort={metric === 'overdue' ? 'descending' : undefined}
                    {...stylex.props(tableStyles.heading)}
                  >
                    Overdue
                  </th>
                  <th scope="col" {...stylex.props(tableStyles.heading)}>
                    Canceled
                  </th>
                  <th
                    scope="col"
                    aria-sort={metric === 'total' ? 'descending' : undefined}
                    {...stylex.props(tableStyles.heading)}
                  >
                    Total
                  </th>
                  <th
                    scope="col"
                    aria-sort={metric === 'completion_rate' ? 'descending' : undefined}
                    {...stylex.props(tableStyles.heading)}
                  >
                    Completion rate
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map(({team, rank}) => (
                  <tr key={team.id}>
                    <td {...stylex.props(tableStyles.cell, styles.muted)}>
                      {rank ?? '—'}
                    </td>
                    <th scope="row" {...stylex.props(tableStyles.cell, tableStyles.team)}>
                      {team.name}
                      {team.key ? (
                        <span {...stylex.props(styles.metadata)}>{team.key}</span>
                      ) : null}
                    </th>
                    <td
                      {...stylex.props(
                        tableStyles.cell,
                        team.completed ? styles.success : styles.muted
                      )}
                    >
                      {team.completed}
                    </td>
                    <td {...stylex.props(tableStyles.cell)}>{team.open}</td>
                    <td
                      {...stylex.props(
                        tableStyles.cell,
                        team.overdue ? styles.danger : styles.muted
                      )}
                    >
                      {team.overdue}
                    </td>
                    <td {...stylex.props(tableStyles.cell, styles.muted)}>
                      {team.canceled}
                    </td>
                    <td {...stylex.props(tableStyles.cell)}>{team.total}</td>
                    <td {...stylex.props(tableStyles.cell)}>
                      {team.completion_rate === null ? '—' : `${team.completion_rate}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p {...stylex.props(styles.empty)}>
            No synced team follow-ups in this scope yet.
          </p>
        )}
        {filtered.length > VISIBLE_TEAMS ? (
          <div {...stylex.props(styles.pagination)}>
            <span role="status" {...stylex.props(styles.muted)}>
              Showing {visible.length} of {filtered.length} teams
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setExpanded(value => !value)}
            >
              {expanded
                ? `Show top ${VISIBLE_TEAMS}`
                : `Show all ${filtered.length} teams`}
            </Button>
          </div>
        ) : null}
      </section>
    </Card>
  );
}

const tableStyles = stylex.create({
  table: {
    width: '100%',
    minWidth: 680,
    borderCollapse: 'collapse',
    textAlign: 'left',
    fontSize: fontSize.sm,
    fontVariantNumeric: 'tabular-nums',
  },
  heading: {
    paddingBlock: space.md,
    paddingInlineEnd: space.lg,
    color: content.secondary,
    fontWeight: 400,
    whiteSpace: 'nowrap',
    borderBottomWidth: 1,
    borderBottomStyle: 'solid',
    borderBottomColor: border.secondary,
  },
  cell: {
    paddingBlock: space.lg,
    paddingInlineEnd: space.lg,
    borderBottomWidth: 1,
    borderBottomStyle: 'solid',
    borderBottomColor: border.secondary,
    verticalAlign: 'middle',
  },
  team: {minWidth: 160, fontWeight: 500, color: content.primary},
  caption: {
    textAlign: 'left',
    color: content.secondary,
    fontSize: fontSize.xs,
    paddingBottom: space.md,
  },
});
