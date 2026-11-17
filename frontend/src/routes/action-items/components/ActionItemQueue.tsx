import * as stylex from '@stylexjs/stylex';
import {Link} from '@tanstack/react-router';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {Pill} from 'components/Pill';

import {PriorityIcon} from '../../$incidentId/components/PriorityIcon';
import type {
  DashboardData,
  DashboardItem,
  DashboardSearch,
  QueueView,
} from '../queries/actionItemDashboardQueryOptions';

import {styles} from './styles';

const VIEWS: {value: QueueView; label: string}[] = [
  {value: 'attention', label: 'Needs attention'},
  {value: 'open', label: 'All open'},
  {value: 'overdue', label: 'Overdue'},
  {value: 'due_soon', label: 'Due soon'},
  {value: 'stalled', label: 'Stalled'},
  {value: 'unassigned', label: 'Unassigned'},
  {value: 'no_priority', label: 'No priority'},
];

function flagLabel(
  flag: DashboardItem['flags'][number],
  item: DashboardItem,
  now: string
) {
  switch (flag) {
    case 'overdue': {
      const days = item.slo_deadline
        ? Math.max(
            1,
            Math.ceil((Date.parse(now) - Date.parse(item.slo_deadline)) / 86_400_000)
          )
        : 0;
      return `${days}d overdue`;
    }
    case 'due_soon':
      return 'Due within 3d';
    case 'stalled':
      return `${item.idle_days}d idle`;
    case 'unassigned':
      return 'Unassigned';
    case 'no_priority':
      return 'No priority';
  }
}

export function ActionItemQueue({
  data,
  search,
  onSearch,
}: {
  data: DashboardData;
  search: DashboardSearch;
  onSearch: (patch: Partial<DashboardSearch>) => void;
}) {
  const {queue, summary} = data;
  const view = search.view ?? 'attention';
  const clear = () => onSearch({view: undefined, assignee: undefined, q: undefined});
  return (
    <Card style={styles.card}>
      <section aria-labelledby="queue-heading">
        <div {...stylex.props(styles.cardHeader)}>
          <div>
            <h2 id="queue-heading" {...stylex.props(styles.heading)}>
              Follow-up queue
            </h2>
            <p {...stylex.props(styles.muted)}>
              Overdue first, then due soon and stalled. Fix the work in Linear.
            </p>
          </div>
          <span role="status" {...stylex.props(styles.muted)}>
            {queue.count} matching {queue.count === 1 ? 'follow-up' : 'follow-ups'}
          </span>
        </div>
        <div {...stylex.props(styles.controls)}>
          <select
            aria-label="Queue view"
            value={view}
            onChange={event => onSearch({view: event.target.value as QueueView})}
            {...stylex.props(styles.control)}
          >
            {VIEWS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label} ({summary[option.value]})
              </option>
            ))}
          </select>
          <select
            aria-label="Queue owner"
            value={search.assignee ?? ''}
            onChange={event => onSearch({assignee: event.target.value || undefined})}
            {...stylex.props(styles.control)}
          >
            <option value="">All owners</option>
            {data.owners.map(owner => (
              <option key={owner.id} value={owner.id}>
                {owner.name} ({owner.open})
              </option>
            ))}
          </select>
          <Button variant="secondary" size="sm" onClick={clear}>
            Clear filters
          </Button>
        </div>
        <form
          role="search"
          aria-label="Search follow-ups"
          key={search.q ?? ''}
          onSubmit={event => {
            event.preventDefault();
            const value = String(new FormData(event.currentTarget).get('q') ?? '').trim();
            onSearch({q: value || undefined});
          }}
          {...stylex.props(styles.controls)}
        >
          <input
            type="search"
            name="q"
            aria-label="Search title, issue, incident, or owner"
            placeholder="Search title, issue, incident, or owner…"
            defaultValue={search.q ?? ''}
            maxLength={200}
            {...stylex.props(styles.control, styles.search)}
          />
          <Button type="submit" variant="secondary" size="sm">
            Search
          </Button>
        </form>
        {queue.results.length ? (
          <div {...stylex.props(styles.scroll)}>
            <table {...stylex.props(styles.table)}>
              <caption {...stylex.props(styles.caption)}>
                Open follow-ups · {VIEWS.find(option => option.value === view)?.label}
              </caption>
              <thead>
                <tr>
                  <th scope="col" {...stylex.props(styles.th)}>
                    Follow-up / incident
                  </th>
                  <th scope="col" {...stylex.props(styles.th)}>
                    Owner
                  </th>
                  <th scope="col" {...stylex.props(styles.th)}>
                    Age
                  </th>
                  <th scope="col" {...stylex.props(styles.th)}>
                    Signals
                  </th>
                </tr>
              </thead>
              <tbody>
                {queue.results.map(item => (
                  <tr key={item.id}>
                    <td {...stylex.props(styles.td, styles.followup)}>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        {...stylex.props(styles.link)}
                      >
                        {item.title}
                      </a>
                      <div {...stylex.props(styles.metadata)}>
                        <PriorityIcon priority={item.priority} />
                        <span>{item.linear_identifier}</span>
                        <Pill variant={item.status}>{item.status}</Pill>
                      </div>
                      <div {...stylex.props(styles.metadata)}>
                        <Link
                          to="/$incidentId"
                          params={{incidentId: item.incident_id}}
                          title={item.incident_title}
                          {...stylex.props(styles.incidentLink)}
                        >
                          {item.incident_id}
                        </Link>
                        <span>{item.incident_severity} incident</span>
                      </div>
                    </td>
                    <td {...stylex.props(styles.td, styles.ownerCell)}>
                      {item.assignee_name ?? 'Unassigned'}
                    </td>
                    <td
                      {...stylex.props(styles.td)}
                      title={`Created ${new Date(item.created_at).toLocaleString()}`}
                    >
                      {item.age_days}d
                    </td>
                    <td {...stylex.props(styles.td)}>
                      <div {...stylex.props(styles.badges)}>
                        {item.flags.length ? (
                          item.flags.map(flag => (
                            <span
                              key={flag}
                              {...stylex.props(
                                styles.badge,
                                flag === 'overdue'
                                  ? styles.dangerBadge
                                  : flag === 'stalled' || flag === 'due_soon'
                                    ? styles.warningBadge
                                    : null
                              )}
                            >
                              {flagLabel(flag, item, data.generated_at)}
                            </span>
                          ))
                        ) : (
                          <span {...stylex.props(styles.muted)}>On track</span>
                        )}
                        {item.idle_days === null ? (
                          <span {...stylex.props(styles.muted)}>Activity unknown</span>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div {...stylex.props(styles.empty)}>
            <p>
              {summary.open === 0
                ? 'No open follow-ups in this scope.'
                : 'No follow-ups match these filters.'}
            </p>
            {summary.open > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  onSearch({view: 'open', assignee: undefined, q: undefined})
                }
              >
                Show all open work
              </Button>
            ) : null}
          </div>
        )}
        <div {...stylex.props(styles.pagination)}>
          <span {...stylex.props(styles.muted)}>
            Page {queue.page} of {queue.pages}
          </span>
          <div {...stylex.props(styles.controls)}>
            <Button
              variant="secondary"
              size="sm"
              disabled={queue.page <= 1}
              onClick={() => onSearch({page: queue.page - 1})}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={queue.page >= queue.pages}
              onClick={() => onSearch({page: queue.page + 1})}
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </Card>
  );
}
