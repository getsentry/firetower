import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {Card} from 'components/Card';

import {IncidentSummary} from './components/IncidentSummary';
import {ParticipantsList} from './components/ParticipantsList';
import {SlackLink} from './components/SlackLink';
import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId/')({
  component: Incident,
  loader: async ({params, context}) =>
    await context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
  pendingComponent: () => <p>Loading incident...</p>,
  errorComponent: () => <p>Something went wrong fetching incident.</p>,
});

function Incident() {
  const params = Route.useParams();
  const {data: incident} = useSuspenseQuery(incidentDetailQueryOptions(params));

  return (
    <div className="space-y-4 p-2">
      <IncidentSummary incident={incident} />

      <div className="flex flex-col gap-4 md:flex-row">
        <section className="flex flex-col gap-4 md:flex-[2]">
          <Card>
            <div className="text-content-muted p-12 text-center">
              <p className="mb-2 text-lg">
                <span role="img" aria-label="fire">
                  🔥
                </span>
              </p>
              <p>Cool features to come</p>
            </div>
          </Card>
        </section>

        <aside className="flex flex-col gap-4 md:flex-1">
          {incident.external_links.slack && (
            <SlackLink
              slackUrl={incident.external_links.slack}
              incidentId={params.incidentId}
            />
          )}
          <ParticipantsList participants={incident.participants} />
        </aside>
      </div>
    </div>
  );
}
