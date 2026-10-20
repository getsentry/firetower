import {useEffect} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';
import {ErrorState} from 'components/ErrorState';
import {GetHelpLink} from 'components/GetHelpLink';

import {ActionItemsList} from './components/ActionItemsList';
import {IncidentDetailSkeleton} from './components/IncidentDetailSkeleton';
import {IncidentSummary} from './components/IncidentSummary';
import {IncidentTimeline} from './components/IncidentTimeline';
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
        redirect={inc_or_redir.redirect}
        message="Old incidents are stored in Jira."
        countdown={5}
      />
    );
  }

  const incident = inc_or_redir.incident;
  return (
    <div {...stylex.props(styles.page)}>
      <IncidentSummary incident={incident} />

      <div {...stylex.props(styles.columns)}>
        <section {...stylex.props(styles.main)}>
          <ActionItemsList
            incidentId={params.incidentId}
            linearUrl={incident.external_links.linear}
          />
          <IncidentTimeline incidentId={incident.id} />
        </section>

        <aside {...stylex.props(styles.sidebar)}>
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

const styles = stylex.create({
  page: {display: 'flex', flexDirection: 'column', rowGap: '16px', padding: '8px'},
  columns: {
    display: 'flex',
    flexDirection: {default: 'column', '@media (min-width: 768px)': 'row'},
    gap: '16px',
  },
  main: {
    order: {default: 2, '@media (min-width: 768px)': 1},
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    flex: {default: null, '@media (min-width: 768px)': '2'},
  },
  sidebar: {
    order: {default: 1, '@media (min-width: 768px)': 2},
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    flex: {default: null, '@media (min-width: 768px)': '1 1 0%'},
  },
});
