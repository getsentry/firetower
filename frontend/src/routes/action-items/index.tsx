import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute, Link} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {EditablePill} from 'components/EditablePill';
import {ErrorState} from 'components/ErrorState';
import {SearchableSelect} from 'components/SearchableSelect';
import {Skeleton} from 'components/Skeleton';
import {RefreshCw} from 'lucide-react';

import {SeveritySchema} from '../types';

import {ActionItemQueue} from './components/ActionItemQueue';
import {DashboardOverview, TeamHotspots} from './components/DashboardOverview';
import {styles} from './components/styles';
import {TeamLeaderboard} from './components/TeamLeaderboard';
import {
  actionItemDashboardQueryOptions,
  DashboardSearchSchema,
  TIME_RANGE_OPTIONS,
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
  const onView = (view: QueueView) => onSearch({view, team: undefined, q: undefined});
  const freshnessIssues =
    data.freshness.unsynced_incidents + data.freshness.stale_incidents;
  const isEmpty = data.summary.open + data.summary.done + data.summary.canceled === 0;

  return (
    <div {...stylex.props(styles.page)}>
      <header>
        <div>
          <h1 {...stylex.props(styles.title)}>Action items</h1>
          <p {...stylex.props(styles.muted)}>
            The health of our incident follow-ups, not just our incidents. Note that this
            page is very much vibe coded to get something up here quickly. Feel free to
            contribute to this page if there's something you want to see.
          </p>
        </div>
      </header>
      <div
        role="group"
        aria-label="Dashboard filters"
        aria-describedby="action-item-scope"
        {...stylex.props(styles.filterRow)}
      >
        <p id="action-item-scope" {...stylex.props(styles.muted, styles.scope)}>
          Scope: follow-ups created in Linear{' '}
          {data.time_range.start ? (
            <>
              since{' '}
              <time dateTime={data.time_range.start}>
                {new Date(data.time_range.start).toLocaleString(undefined, {
                  timeZone: 'UTC',
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </time>{' '}
              UTC. Older open and overdue work is excluded; choose All time for the full
              backlog.
            </>
          ) : (
            'across all time, including the full open backlog.'
          )}
        </p>
        <div {...stylex.props(styles.controls, styles.filterControls)}>
          <SearchableSelect
            label="Time range"
            value={search.time_range ?? 'all'}
            options={TIME_RANGE_OPTIONS}
            onChange={time_range => {
              void navigate({
                search: previous => ({
                  severity: previous.severity,
                  time_range: time_range === 'all' ? undefined : time_range,
                }),
              });
            }}
          />
          <div
            role="group"
            aria-label="Incident severity"
            {...stylex.props(styles.controls)}
          >
            <span {...stylex.props(styles.muted)}>Incident severity</span>
            <EditablePill
              value={search.severity ?? 'All'}
              options={['All', ...SeveritySchema.options] as const}
              getVariant={value => (value === 'All' ? 'default' : value)}
              onSave={async value => {
                await navigate({
                  search: previous => ({
                    time_range: previous.time_range,
                    severity: value === 'All' ? undefined : value,
                  }),
                });
              }}
            />
          </div>
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
      </div>
      {data.freshness.outside_refresh_window_incidents > 0 ? (
        <p {...stylex.props(styles.muted)}>
          {data.freshness.outside_refresh_window_incidents} linked incident
          {data.freshness.outside_refresh_window_incidents === 1 ? '' : 's'} created
          before{' '}
          <time dateTime={data.freshness.auto_refresh_cutoff}>
            {new Date(data.freshness.auto_refresh_cutoff).toLocaleString(undefined, {
              timeZone: 'UTC',
              dateStyle: 'medium',
              timeStyle: 'short',
            })}
          </time>{' '}
          UTC {data.freshness.outside_refresh_window_incidents === 1 ? 'is' : 'are'}{' '}
          outside the {data.freshness.auto_refresh_months}-month automatic refresh window.
          Older cached follow-ups remain available; use the incident's Sync action items
          button to update them.
        </p>
      ) : null}
      {isRefetchError ? (
        <p role="alert" {...stylex.props(styles.warningBox)}>
          Refresh failed. Showing the previous snapshot; try again.
        </p>
      ) : null}
      {freshnessIssues > 0 ||
      data.summary.unknown_activity > 0 ||
      data.summary.unknown_team > 0 ? (
        <p
          role="status"
          aria-label="Action item data freshness"
          {...stylex.props(styles.warningBox)}
        >
          Automatic sync coverage for incidents created in the last{' '}
          {data.freshness.auto_refresh_months} months: {data.freshness.unsynced_incidents}{' '}
          never synced; {data.freshness.stale_incidents} not synced in 24h. Selected open
          follow-ups missing activity timestamps: {data.summary.unknown_activity}; missing
          Linear team metadata: {data.summary.unknown_team}. Open an incident and use Sync
          action items to update its cached data.
        </p>
      ) : null}
      {isEmpty ? (
        <Card style={styles.card}>
          <h2 {...stylex.props(styles.heading)}>No synced follow-ups yet</h2>
          <p {...stylex.props(styles.muted)}>
            Create child issues under an incident's Linear ticket, then use Sync action
            items on the incident to load them here. Incidents created in the last{' '}
            {data.freshness.auto_refresh_months} months are also refreshed hourly.{' '}
            <Link to="/" {...stylex.props(styles.incidentLink)}>
              Browse incidents
            </Link>
          </p>
        </Card>
      ) : null}
      <DashboardOverview data={data} onView={onView} />
      <TeamLeaderboard data={data} rangeLabel={data.time_range.label} />
      <div {...stylex.props(styles.lowerGrid)}>
        <ActionItemQueue data={data} search={search} onSearch={onSearch} />
        <TeamHotspots
          data={data}
          onTeam={team => onSearch({team, view: 'open', q: undefined})}
        />
      </div>
      <p {...stylex.props(styles.muted)}>
        Includes follow-ups from closed incidents. Time range and severity scope the
        entire dashboard; queue and team-progress controls filter independently.
        <br />
        Cached Linear data · hourly sync for incidents created in the last{' '}
        {data.freshness.auto_refresh_months} months · snapshot{' '}
        <time dateTime={data.generated_at}>
          {new Date(data.generated_at).toLocaleString()}
        </time>
        .
        {data.freshness.oldest_sync_at ? (
          <>
            {' '}
            Oldest cached incident sync:{' '}
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
