import {createFileRoute} from '@tanstack/react-router';
import {zodValidator} from '@tanstack/zod-adapter';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';
import {z} from 'zod';

import {AvailabilityPage} from './components/AvailabilityPage';
import {availabilityQueryOptions, PeriodSchema} from './queries/availabilityQueryOptions';

const availabilitySearchSchema = z.object({
  period: PeriodSchema.optional(),
});

export const Route = createFileRoute('/availability/')({
  component: AvailabilityPage,
  validateSearch: zodValidator(availabilitySearchSchema),
  loader: async ({context}) => {
    await context.queryClient.ensureQueryData(availabilityQueryOptions());
  },
  errorComponent: () => (
    <ErrorState
      title="Something went wrong fetching availability data"
      description={
        <p>
          Try refreshing the page, or if that doesn't work, come chat with us in{' '}
          <GetHelpLink />.
        </p>
      }
    />
  ),
});
