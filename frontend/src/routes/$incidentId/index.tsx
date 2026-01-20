import {useEffect} from 'react';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {Card} from 'components/Card';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';

import {IncidentDetailSkeleton} from './components/IncidentDetailSkeleton';
import {IncidentSummary} from './components/IncidentSummary';
import {LinksList} from './components/LinksList';
import {MilestonesCard} from './components/MilestonesCard';
import {ParticipantsList} from './components/ParticipantsList';
import {Redirect} from './components/Redirect';
import {SlackLink} from './components/SlackLink';
import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId/')({
  component: Incident,
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

function Incident() {
  const params = Route.useParams();
  const {data: inc_or_redir} = useSuspenseQuery(incidentDetailQueryOptions(params));

  useEffect(() => {
    document.title = `${params.incidentId} • Firetower`;
    return () => {
      document.title = 'Firetower';
    };
  }, [params.incidentId]);

  if ('redirect' in inc_or_redir) {
    return (
      <Redirect
        redirect={() => inc_or_redir['redirect']}
        message="Old incidents are stored in Jira."
        countdown={5}
      />
    );
  }

  const incident = inc_or_redir.incident;
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
          <LinksList externalLinks={incident.external_links} />
          <MilestonesCard incident={incident} />
          <ParticipantsList
            incidentId={params.incidentId}
            participants={incident.participants}
          />
        </aside>
      </div>
    </div>
  );
}
