import {createFileRoute} from '@tanstack/react-router';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';

import {IncidentDetailSkeleton} from './components/IncidentDetailSkeleton';
import {IncidentPage} from './components/IncidentPage';
import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId/')({
  component: IncidentPage,
  loader: async ({params, context}) =>
    await context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
  pendingComponent: () => <IncidentDetailSkeleton />,
  errorComponent: () => (
    <ErrorState
      title="We couldn't find that incident"
      description={
        <>
          <p>You don't have access or it doesn't exist.</p>
          <p>
            If you think this is a bug, let us know in <GetHelpLink />.
          </p>
        </>
      }
      showBackButton
    />
  ),
});
