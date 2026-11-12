import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {z} from 'zod';

import {IncidentListSkeleton} from './components/IncidentListSkeleton';
import {IncidentsLayout, IncidentsPage} from './components/IncidentsPage';
import {incidentsQueryOptions} from './queries/incidentsQueryOptions';

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

export const Route = createFileRoute('/')({
  component: IncidentsPage,
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
          <p>
            Try refreshing the page, or if that doesn't work, come chat with us in{' '}
            <GetHelpLink />.
          </p>
        }
      />
    </IncidentsLayout>
  ),
});
