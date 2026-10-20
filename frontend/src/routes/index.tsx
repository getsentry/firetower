import {createContext, useContext, useEffect, useRef, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useSuspenseInfiniteQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Button} from 'components/Button';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {Spinner} from 'components/Spinner';
import {arraysEqual} from 'utils/arrays';
import {z} from 'zod';

import {content, space} from '../styles/tokens.stylex';

import {FilterPanel, FilterTrigger} from './components/AdvancedFilters';
import {CreateIncidentDialog} from './components/CreateIncidentDialog';
import {IncidentCard} from './components/IncidentCard';
import {IncidentListSkeleton} from './components/IncidentListSkeleton';
import {StatusFilter} from './components/StatusFilter';
import {useActiveFilters} from './components/useActiveFilters';
import {incidentsQueryOptions} from './queries/incidentsQueryOptions';
import {STATUS_FILTER_GROUPS} from './types';

const CreateDialogContext = createContext<{
  showCreateDialog: boolean;
  setShowCreateDialog: (open: boolean) => void;
}>({showCreateDialog: false, setShowCreateDialog: () => {}});

const stringArrayPreprocess = z
  .preprocess(val => {
    if (val === undefined) return undefined;
    if (Array.isArray(val) && val.every(v => typeof v === 'string')) return val;
    if (typeof val === 'string') return [val];
    return [String(val)];
  }, z.array(z.string()).optional())
  .optional();

const incidentListSearchSchema = z.object({
  status: stringArrayPreprocess,
  severity: stringArrayPreprocess,
  service_tier: stringArrayPreprocess,
  affected_service: stringArrayPreprocess,
  root_cause: stringArrayPreprocess,
  impact_type: stringArrayPreprocess,
  affected_region: stringArrayPreprocess,
  captain: stringArrayPreprocess,
  reporter: stringArrayPreprocess,
  participant: stringArrayPreprocess,
  created_after: z.string().optional(),
  created_before: z.string().optional(),
});

function IncidentsLayout({
  children,
  showCreateButton = true,
}: {
  children: React.ReactNode;
  showCreateButton?: boolean;
}) {
  const {activeCount} = useActiveFilters();
  const [open, setOpen] = useState(activeCount > 0);
  const {setShowCreateDialog} = useContext(CreateDialogContext);

  return (
    <div {...stylex.props(styles.layout)}>
      <div {...stylex.props(styles.toolbar)}>
        <StatusFilter />
        <div {...stylex.props(styles.actions)}>
          {showCreateButton ? (
            <Button variant="primary" size="sm" onClick={() => setShowCreateDialog(true)}>
              Create Incident
            </Button>
          ) : null}
          <FilterTrigger open={open} onToggle={() => setOpen(prev => !prev)} />
        </div>
      </div>
      {open ? <FilterPanel /> : null}
      {children}
    </div>
  );
}

function IncidentsPageWrapper({children}: {children: React.ReactNode}) {
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  return (
    <CreateDialogContext.Provider value={{showCreateDialog, setShowCreateDialog}}>
      {children}
      <CreateIncidentDialog
        isOpen={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
      />
    </CreateDialogContext.Provider>
  );
}

export const Route = createFileRoute('/')({
  component: Index,
  validateSearch: zodValidator(incidentListSearchSchema),
  loaderDeps: ({search}) => search,
  loader: async ({deps, context}) => {
    const options = incidentsQueryOptions(deps);
    await context.queryClient.prefetchInfiniteQuery(options);
  },
  pendingComponent: () => (
    <IncidentsLayout showCreateButton={false}>
      <IncidentListSkeleton />
    </IncidentsLayout>
  ),
  errorComponent: () => (
    <IncidentsLayout showCreateButton={false}>
      <ErrorState
        title="Something went wrong fetching incidents"
        description={
          <>
            Try refreshing the page, or if that doesn't work, come chat with us in{' '}
            <GetHelpLink />.
          </>
        }
      />
    </IncidentsLayout>
  ),
});

const STORAGE_KEY = 'firetower_list_search';

function IncidentsEmptyState({status}: {status?: string[]}) {
  if (!status || arraysEqual(status, STATUS_FILTER_GROUPS.active)) {
    return (
      <div {...stylex.props(styles.emptyState)}>
        <p>There are no active incidents! {String.fromCodePoint(0x1f389)}</p>
      </div>
    );
  }
  if (arraysEqual(status, STATUS_FILTER_GROUPS.review)) {
    return (
      <div {...stylex.props(styles.emptyState)}>
        <p>There are no incidents in review.</p>
      </div>
    );
  }
  return (
    <div {...stylex.props(styles.emptyState)}>
      <p {...stylex.props(styles.emptyMessage)}>
        There are no incidents matching those filters.
      </p>
      <p>
        If you think this is a bug, let us know in <GetHelpLink />.
      </p>
    </div>
  );
}

function Index() {
  const params = Route.useSearch();
  const {
    data: incidents,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useSuspenseInfiniteQuery(incidentsQueryOptions(params));

  const observerTarget = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  }, [params]);

  useEffect(() => {
    const target = observerTarget.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      {threshold: 0.1}
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  return (
    <IncidentsPageWrapper>
      <IncidentsLayout>
        {incidents.length === 0 ? (
          <IncidentsEmptyState status={params.status} />
        ) : (
          <>
            <ul {...stylex.props(styles.incidents)}>
              {incidents.map(incident => (
                <li key={incident.id}>
                  <IncidentCard incident={incident} />
                </li>
              ))}
            </ul>

            <div ref={observerTarget} {...stylex.props(styles.loading)}>
              {isFetchingNextPage ? <Spinner size="md" /> : null}
            </div>
          </>
        )}
      </IncidentsLayout>
    </IncidentsPageWrapper>
  );
}

const styles = stylex.create({
  layout: {gap: space.lg, display: 'flex', flexDirection: 'column'},
  toolbar: {display: 'flex', alignItems: 'center', justifyContent: 'space-between'},
  actions: {gap: space.sm, display: 'flex', alignItems: 'center'},
  emptyState: {color: content.secondary, paddingBlock: 48, textAlign: 'center'},
  emptyMessage: {marginBottom: space.lg},
  incidents: {
    gap: space.lg,
    display: 'flex',
    listStyleType: 'none',
    flexDirection: 'column',
  },
  loading: {paddingBlock: space.xl, display: 'flex', justifyContent: 'center'},
});
