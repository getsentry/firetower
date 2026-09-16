import {createContext, useContext, useEffect, useRef, useState} from 'react';
import {useSuspenseInfiniteQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {Button} from 'components/Button';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {Spinner} from 'components/Spinner';
import {arraysEqual} from 'utils/arrays';
import {z} from 'zod';

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
    <div className="gap-space-lg flex flex-col">
      <div className="flex items-center justify-between">
        <StatusFilter />
        <div className="gap-space-sm flex items-center">
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
  // Component to render
  component: Index,
  // Validate search params with zod schema
  validateSearch: zodValidator(incidentListSearchSchema),
  // Extract search params needed for loader
  loaderDeps: ({search}) => search,
  // Define loader with loaderDeps and context (context has queryClient)
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
      <div className="text-content-secondary py-space-4xl text-center">
        <p>There are no active incidents! {String.fromCodePoint(0x1f389)}</p>
      </div>
    );
  }
  if (arraysEqual(status, STATUS_FILTER_GROUPS.review)) {
    return (
      <div className="text-content-secondary py-space-4xl text-center">
        <p>There are no incidents in review.</p>
      </div>
    );
  }
  return (
    <div className="text-content-secondary py-space-4xl text-center">
      <p className="mb-space-lg">There are no incidents matching those filters.</p>
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

  // Store current search params in sessionStorage whenever they change
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  }, [params]);

  // Infinite scroll observer
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
            <ul className="gap-space-lg flex list-none flex-col">
              {incidents.map(incident => (
                <li key={incident.id}>
                  <IncidentCard incident={incident} />
                </li>
              ))}
            </ul>

            {/* Intersection observer target */}
            <div ref={observerTarget} className="py-space-xl flex justify-center">
              {isFetchingNextPage ? <Spinner size="md" /> : null}
            </div>
          </>
        )}
      </IncidentsLayout>
    </IncidentsPageWrapper>
  );
}
