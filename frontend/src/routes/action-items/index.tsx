import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute, Link} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {Skeleton} from 'components/Skeleton';
import {RefreshCw} from 'lucide-react';

import {ActionItemQueue} from './components/ActionItemQueue';
import {DashboardOverview, OwnerHotspots} from './components/DashboardOverview';
import {styles} from './components/styles';
import {
  actionItemDashboardQueryOptions,
  DashboardSearchSchema,
  type DashboardSearch,
  type QueueView,
} from './queries/actionItemDashboardQueryOptions';

export const Route = createFileRoute('/action-items/')({
  component: ActionItemsDashboard,
  validateSearch: zodValidator(DashboardSearchSchema),
  loaderDeps: ({search}) => search,
  loader: ({context, deps}) =>
    context.queryClient.ensureQueryData(actionItemDashboardQueryOptions(deps)),
  pendingComponent: () => (
    <div
      {...stylex.props(styles.page)}
      role="status"
      aria-label="Loading action item dashboard"
    >
      <h1 {...stylex.props(styles.title)}>Action items</h1>
      <Skeleton style={styles.skeleton} />
      <Skeleton style={styles.skeleton} />
    </div>
  ),
  errorComponent: () => (
    <ErrorState
      title="Unable to load action items"
      description={
        <>
          <p>The dashboard could not be fetched. Your action items have not changed.</p>
          <Button onClick={() => window.location.reload()}>Try again</Button>
        </>
      }
    />
  ),
});

function ActionItemsDashboard() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const {data, refetch, isFetching, isRefetchError} = useSuspenseQuery(
    actionItemDashboardQueryOptions(search)
  );
  const onSearch = (patch: Partial<DashboardSearch>) => {
    void navigate({search: previous => ({...previous, page: undefined, ...patch})});
  };
  const onView = (view: QueueView) => onSearch({view, assignee: undefined, q: undefined});
  const freshnessIssues =
    data.freshness.unsynced_incidents + data.freshness.stale_incidents;
  const isEmpty = data.summary.open + data.summary.done + data.summary.canceled === 0;

  return (
    <div {...stylex.props(styles.page)}>
      <header {...stylex.props(styles.header)}>
        <div>
          <p {...stylex.props(styles.eyebrow)}>
            Learn from incidents. Finish the follow-through.
          </p>
          <h1 {...stylex.props(styles.title)}>Action items</h1>
          <p {...stylex.props(styles.muted)}>
            The health of our incident follow-ups, not just our incidents.
          </p>
        </div>
        <div {...stylex.props(styles.controls)}>
          <label htmlFor="dashboard-severity" {...stylex.props(styles.muted)}>
            Incident severity
          </label>
          <select
            id="dashboard-severity"
            value={search.severity ?? ''}
            onChange={event => {
              const severity = event.target.value as DashboardSearch['severity'];
              void navigate({search: severity ? {severity} : {}});
            }}
            {...stylex.props(styles.control)}
          >
            <option value="">All severities</option>
            {(['P0', 'P1', 'P2', 'P3', 'P4'] as const).map(severity => (
              <option key={severity} value={severity}>
                {severity}
              </option>
            ))}
          </select>
          <Button
            variant="secondary"
            size="sm"
            disabled={isFetching}
            onClick={() => {
              void refetch();
            }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            {isFetching ? 'Refreshing…' : 'Refresh dashboard'}
          </Button>
        </div>
      </header>
      {isRefetchError ? (
        <p role="alert" {...stylex.props(styles.warningBox)}>
          Refresh failed. Showing the previous snapshot; try again.
        </p>
      ) : null}
      {freshnessIssues > 0 || data.summary.unknown_activity > 0 ? (
        <p role="status" {...stylex.props(styles.warningBox)}>
          Data may be incomplete: {data.freshness.unsynced_incidents} linked incidents
          have never synced, {data.freshness.stale_incidents} have not synced in 24h, and{' '}
          {data.summary.unknown_activity} open follow-ups have no activity timestamp. The
          hourly Linear sync fills these in. Open an incident to sync it individually.
        </p>
      ) : null}
      {isEmpty ? (
        <Card style={styles.card}>
          <h2 {...stylex.props(styles.heading)}>No synced follow-ups yet</h2>
          <p {...stylex.props(styles.muted)}>
            Create child issues under an incident's Linear ticket. They will appear after
            the next sync.{' '}
            <Link to="/" {...stylex.props(styles.incidentLink)}>
              Browse incidents
            </Link>
          </p>
        </Card>
      ) : null}
      <DashboardOverview data={data} onView={onView} />
      <div {...stylex.props(styles.lowerGrid)}>
        <ActionItemQueue data={data} search={search} onSearch={onSearch} />
        <OwnerHotspots
          data={data}
          onOwner={assignee => onSearch({assignee, view: 'open', q: undefined})}
        />
      </div>
      <p {...stylex.props(styles.muted)}>
        All open work is included regardless of age or incident status. Severity scopes
        the entire dashboard; queue filters only affect the queue.
        <br />
        Cached Linear data · synced hourly · snapshot{' '}
        <time dateTime={data.generated_at}>
          {new Date(data.generated_at).toLocaleString()}
        </time>
        .
        {data.freshness.oldest_sync_at ? (
          <>
            {' '}
            Oldest incident sync:{' '}
            <time dateTime={data.freshness.oldest_sync_at}>
              {new Date(data.freshness.oldest_sync_at).toLocaleString()}
            </time>
            .
          </>
        ) : null}
      </p>
    </div>
  );
}
