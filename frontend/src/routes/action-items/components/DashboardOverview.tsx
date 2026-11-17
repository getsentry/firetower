import * as stylex from '@stylexjs/stylex';
import {Card} from 'components/Card';

import type {DashboardData, QueueView} from '../queries/actionItemDashboardQueryOptions';

import {styles} from './styles';

function weekLabel(start: string) {
  return new Date(`${start}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export function DashboardOverview({
  data,
  onView,
}: {
  data: DashboardData;
  onView: (view: QueueView) => void;
}) {
  const {summary, weeks, aging} = data;
  const maxFlow = Math.max(1, ...weeks.flatMap(week => [week.created, week.completed]));
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
          <span {...stylex.props(styles.metricLabel)}>Completed · last 30 days</span>
          <strong {...stylex.props(styles.metricValue, styles.success)}>
            {summary.completed_30d}
          </strong>
          <span {...stylex.props(styles.muted)}>
            {summary.created_30d} created in the same period
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
            <div {...stylex.props(styles.flowChart)}>
              {weeks.map(week => (
                <div
                  key={week.start}
                  role="img"
                  aria-label={`Week of ${weekLabel(week.start)}: ${week.created} created, ${week.completed} completed`}
                  {...stylex.props(styles.week)}
                >
                  <div {...stylex.props(styles.barPair)} aria-hidden="true">
                    <div {...stylex.props(styles.barColumn)}>
                      <span>{week.created}</span>
                      <div
                        {...stylex.props(
                          styles.bar((week.created / maxFlow) * 88),
                          styles.createdFill
                        )}
                      />
                    </div>
                    <div {...stylex.props(styles.barColumn)}>
                      <span>{week.completed}</span>
                      <div
                        {...stylex.props(
                          styles.bar((week.completed / maxFlow) * 88),
                          styles.completedFill
                        )}
                      />
                    </div>
                  </div>
                  <span {...stylex.props(styles.weekLabel)} aria-hidden="true">
                    {weekLabel(week.start)}
                  </span>
                </div>
              ))}
            </div>
            <figcaption {...stylex.props(styles.caption)}>
              Last 8 weeks · UTC · current week is partial. Canceled work is not counted
              as completed.
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
              Age since creation in Linear · all open follow-ups, including closed
              incidents.
            </figcaption>
          </figure>
        </Card>
      </div>
    </>
  );
}

export function OwnerHotspots({
  data,
  onOwner,
}: {
  data: DashboardData;
  onOwner: (id: string) => void;
}) {
  const {summary} = data;
  return (
    <aside {...stylex.props(styles.aside)}>
      <Card style={styles.card}>
        <h2 {...stylex.props(styles.heading)}>Delivery · last 30 days</h2>
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
          {summary.on_time_sample} completed follow-ups with an SLO target. No target is
          not the same as on time.
        </p>
        <div {...stylex.props(styles.cardHeader)}>
          <h2 {...stylex.props(styles.heading)}>Where help is needed</h2>
        </div>
        <p {...stylex.props(styles.muted)}>
          Owners ranked by overdue work, then stalled work.
        </p>
        <ul {...stylex.props(styles.ownerList)}>
          {data.owners.slice(0, 5).map(owner => (
            <li key={owner.id}>
              <button
                type="button"
                onClick={() => onOwner(owner.id)}
                {...stylex.props(styles.ownerButton)}
              >
                <span {...stylex.props(styles.ownerName)}>
                  {owner.name}
                  <span {...stylex.props(styles.metadata)}>
                    {owner.open} open · {owner.stalled} stalled
                  </span>
                </span>
                <span
                  {...stylex.props(
                    styles.ownerCount,
                    owner.overdue ? styles.danger : styles.muted
                  )}
                >
                  {owner.overdue} overdue
                </span>
              </button>
            </li>
          ))}
        </ul>
        {data.owners.length === 0 ? (
          <p {...stylex.props(styles.empty)}>No open work.</p>
        ) : null}
        {data.owners.length > 5 ? (
          <p {...stylex.props(styles.caption)}>
            Top 5 of {data.owners.length} owners. Use the queue's owner filter to see
            anyone.
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
              SLO deadlines use the configured priority targets and the issue's original
              creation time. Low and unset priority have no target. Stalled means no issue
              update in Linear for {data.stalled_days} days, not time since Firetower's
              last sync.
            </p>
            <p>
              Delivery metrics use the completion timestamps of currently completed Linear
              issues. They are not a historical status ledger. Reopened and canceled items
              are not counted as completed.
            </p>
            <p>
              All-time totals: {summary.done} completed, {summary.canceled} canceled.{' '}
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
