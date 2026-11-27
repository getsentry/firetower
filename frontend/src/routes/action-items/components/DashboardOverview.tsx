import * as stylex from '@stylexjs/stylex';
import {Card} from 'components/Card';

import type {DashboardData, QueueView} from '../queries/actionItemDashboardQueryOptions';

import {styles} from './styles';

export function DashboardOverview({
  data,
  onView,
}: {
  data: DashboardData;
  onView: (view: QueueView) => void;
}) {
  const {summary, trend, aging} = data;
  const maxFlow = Math.max(
    1,
    ...trend.buckets.flatMap(bucket => [bucket.created, bucket.completed])
  );
  const maxAge = Math.max(1, ...aging.map(bucket => bucket.count));
  const metrics = [
    {
      label: 'Open follow-ups',
      value: summary.open,
      detail: `${summary.todo} to do · ${summary.in_progress} in progress`,
      view: 'open' as const,
    },
    {
      label: 'Overdue',
      value: summary.overdue,
      detail: `${summary.due_soon} due in the next ${data.due_soon_days} days`,
      view: 'overdue' as const,
    },
    {
      label: 'Stalled',
      value: summary.stalled,
      detail: `No Linear update in ${data.stalled_days}+ days`,
      view: 'stalled' as const,
    },
  ];
  return (
    <>
      <div {...stylex.props(styles.metrics)} aria-label="Action item health">
        {metrics.map(metric => (
          <button
            type="button"
            key={metric.label}
            onClick={() => onView(metric.view)}
            {...stylex.props(styles.metric, styles.metricButton)}
          >
            <span {...stylex.props(styles.metricLabel)}>{metric.label}</span>
            <strong
              {...stylex.props(
                styles.metricValue,
                metric.view === 'overdue' && metric.value > 0 ? styles.danger : null
              )}
            >
              {metric.value}
            </strong>
            <span {...stylex.props(styles.muted)}>{metric.detail}</span>
          </button>
        ))}
        <div {...stylex.props(styles.metric)}>
          <span {...stylex.props(styles.metricLabel)}>
            Completed · {data.time_range.label.toLowerCase()}
          </span>
          <strong {...stylex.props(styles.metricValue, styles.success)}>
            {summary.completed_count}
          </strong>
          <span {...stylex.props(styles.muted)}>
            {summary.created_count} created in the selected range
          </span>
        </div>
      </div>
      <div {...stylex.props(styles.charts)}>
        <Card style={styles.card}>
          <figure aria-labelledby="flow-heading">
            <div {...stylex.props(styles.cardHeader)}>
              <h2 id="flow-heading" {...stylex.props(styles.heading)}>
                Are we keeping up?
              </h2>
              <div {...stylex.props(styles.legend)}>
                <span {...stylex.props(styles.legendItem)}>
                  <span {...stylex.props(styles.dot, styles.createdFill)} />
                  Created
                </span>
                <span {...stylex.props(styles.legendItem)}>
                  <span {...stylex.props(styles.dot, styles.completedFill)} />
                  Completed
                </span>
              </div>
            </div>
            <div {...stylex.props(styles.scroll)}>
              <div {...stylex.props(styles.flowChart(trend.buckets.length))}>
                {trend.buckets.map(bucket => (
                  <div
                    key={bucket.start}
                    role="img"
                    aria-label={`${bucket.label}: ${bucket.created} created, ${bucket.completed} completed`}
                    title={`${new Date(bucket.start).toUTCString()} – ${new Date(bucket.end).toUTCString()}`}
                    {...stylex.props(styles.trendBucket)}
                  >
                    <div {...stylex.props(styles.barPair)} aria-hidden="true">
                      <div {...stylex.props(styles.barColumn)}>
                        <span>{bucket.created}</span>
                        <div
                          {...stylex.props(
                            styles.bar((bucket.created / maxFlow) * 88),
                            styles.createdFill
                          )}
                        />
                      </div>
                      <div {...stylex.props(styles.barColumn)}>
                        <span>{bucket.completed}</span>
                        <div
                          {...stylex.props(
                            styles.bar((bucket.completed / maxFlow) * 88),
                            styles.completedFill
                          )}
                        />
                      </div>
                    </div>
                    <span {...stylex.props(styles.periodLabel)} aria-hidden="true">
                      {bucket.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <figcaption {...stylex.props(styles.caption)}>
              {data.time_range.label} · {trend.interval} · UTC · boundary periods are
              partial. Canceled work is not counted as completed.
            </figcaption>
          </figure>
        </Card>
        <Card style={styles.card}>
          <figure aria-labelledby="age-heading">
            <div {...stylex.props(styles.cardHeader)}>
              <h2 id="age-heading" {...stylex.props(styles.heading)}>
                How old is the backlog?
              </h2>
              <span {...stylex.props(styles.legend, styles.legendItem)}>
                <span {...stylex.props(styles.dot, styles.overdueFill)} />
                Overdue
              </span>
            </div>
            <div {...stylex.props(styles.agingRows)}>
              {aging.map(bucket => (
                <div
                  key={bucket.label}
                  aria-label={`${bucket.label}: ${bucket.count} open, ${bucket.overdue} overdue`}
                  {...stylex.props(styles.agingRow)}
                >
                  <span>{bucket.label}</span>
                  <div {...stylex.props(styles.track)} aria-hidden="true">
                    <div {...stylex.props(styles.ageBar((bucket.count / maxAge) * 100))}>
                      <div
                        {...stylex.props(
                          styles.overdueBar(
                            bucket.count ? (bucket.overdue / bucket.count) * 100 : 0
                          )
                        )}
                      />
                    </div>
                  </div>
                  <strong>{bucket.count}</strong>
                </div>
              ))}
            </div>
            <figcaption {...stylex.props(styles.caption)}>
              Age since creation in Linear · open follow-ups in the selected range,
              including closed incidents.
            </figcaption>
          </figure>
        </Card>
      </div>
    </>
  );
}

export function TeamHotspots({
  data,
  onTeam,
}: {
  data: DashboardData;
  onTeam: (id: string) => void;
}) {
  const {summary} = data;
  const atRisk = data.teams.filter(team => team.overdue > 0 || team.stalled > 0);
  return (
    <aside {...stylex.props(styles.aside)}>
      <Card style={styles.card}>
        <h2 {...stylex.props(styles.heading)}>
          Delivery · {data.time_range.label.toLowerCase()}
        </h2>
        <dl {...stylex.props(styles.facts)}>
          <div>
            <dt {...stylex.props(styles.muted)}>Median time to finish</dt>
            <dd {...stylex.props(styles.factValue)}>
              {summary.median_completion_days === null
                ? '—'
                : `${summary.median_completion_days}d`}
            </dd>
          </div>
          <div>
            <dt {...stylex.props(styles.muted)}>Completed on time</dt>
            <dd {...stylex.props(styles.factValue)}>
              {summary.on_time_percent === null ? '—' : `${summary.on_time_percent}%`}
            </dd>
          </div>
        </dl>
        <p {...stylex.props(styles.caption)}>
          {summary.on_time_sample} completed follow-ups with a deadline. No deadline is
          not the same as on time.
        </p>
        <hr {...stylex.props(styles.divider)} />
        <p {...stylex.props(styles.muted)}>
          Linear teams with overdue or stalled follow-ups.
        </p>
        <ul {...stylex.props(styles.teamList)}>
          {atRisk.slice(0, 5).map(team => (
            <li key={team.id}>
              <button
                type="button"
                onClick={() => onTeam(team.id)}
                {...stylex.props(styles.teamButton)}
              >
                <span {...stylex.props(styles.teamName)}>
                  {team.name}
                  <span {...stylex.props(styles.metadata)}>
                    {team.open} open · {team.stalled} stalled
                  </span>
                </span>
                <span
                  {...stylex.props(
                    styles.teamCount,
                    team.overdue ? styles.danger : styles.muted
                  )}
                >
                  {team.overdue} overdue
                </span>
              </button>
            </li>
          ))}
        </ul>
        {atRisk.length === 0 ? (
          <p {...stylex.props(styles.empty)}>No overdue or stalled follow-ups.</p>
        ) : null}
        {atRisk.length > 5 ? (
          <p {...stylex.props(styles.caption)}>
            Showing 5 of {atRisk.length} teams. Use the queue's team filter to see any
            team.
          </p>
        ) : null}
      </Card>
      <Card style={styles.card}>
        <details {...stylex.props(styles.details)}>
          <summary {...stylex.props(styles.summary)}>How to read this dashboard</summary>
          <div {...stylex.props(styles.detailsBody)}>
            <p>
              Open means Todo or In Progress. The attention queue includes overdue, due
              soon, stalled, unassigned, and unprioritized work; an item can have several
              signals.
            </p>
            <p>
              Deadlines use the explicit Linear due date first, then Linear's SLA
              deadline, then the configured priority SLO from the issue's creation time.
              Date-only due dates run through the end of that date in UTC. A low or
              unprioritized item can still have an explicit deadline; items without any
              deadline are excluded from overdue, due-soon, and on-time metrics but still
              count toward open work, aging, and stalled work.
            </p>
            <p>
              Incidents created in the last {data.freshness.auto_refresh_months} months
              are synced hourly. Older incidents are refreshed on demand when viewing
              their action items or syncing manually. Use the incident's Sync action items
              button to fetch current data at any age, then refresh this dashboard.
              Clearing a due date falls back to the remaining SLA or priority target;
              Refresh dashboard alone only reloads cached data.
            </p>
            <p>
              Stalled means no issue update in Linear for {data.stalled_days} days, not
              time since Firetower's last sync. Teams are the child issues' Linear teams,
              not the incident's team or individual assignees. Missing team metadata is
              shown as Team not synced until the next sync.
            </p>
            <p>
              Delivery metrics use the completion timestamps of currently completed Linear
              issues. They are not a historical status ledger. Reopened and canceled items
              are not counted as completed. On-time comparisons use the currently synced
              deadline, not a historical deadline snapshot.
            </p>
            <p>
              The global time range selects follow-ups by their Linear creation time, not
              the parent incident's date. Finite ranges exclude older open and overdue
              work; choose All time for the full backlog. Team progress uses current
              statuses in that same range, including completed-only teams. Total includes
              canceled items; completion rate is completed divided by completed plus open
              work, excluding canceled items. Delivery metrics additionally require a
              valid completion timestamp. Never-synced and stale-sync counts cover only
              visible linked incidents within the automatic refresh window, independent of
              the selected time range. Outside-window incidents are reported separately;
              their cached follow-ups remain available.
            </p>
            <p>
              Totals in this range: {summary.done} completed, {summary.canceled} canceled.{' '}
              {summary.unknown_completion} completed items lack a completion date and are
              excluded from delivery metrics. {summary.unknown_activity} open items lack
              activity dates and are not classified as stalled.
            </p>
            <p>
              Only incidents you can access are included. Canceled incidents are excluded.{' '}
              {data.freshness.unlinked_incidents} incidents have no linked Linear parent;
              their follow-ups may not be represented.
            </p>
          </div>
        </details>
      </Card>
    </aside>
  );
}
