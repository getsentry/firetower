import {useEffect} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {getRouteApi} from '@tanstack/react-router';

import {incidentDetailQueryOptions} from '../queries/incidentDetailQueryOptions';

import {ActionItemsList} from './ActionItemsList';
import {IncidentSummary} from './IncidentSummary';
import {IncidentTimeline} from './IncidentTimeline';
import {LinksList} from './LinksList';
import {MilestonesCard} from './MilestonesCard';
import {ParticipantsList} from './ParticipantsList';
import {Redirect} from './Redirect';
import {SlackLink} from './SlackLink';

const route = getRouteApi('/$incidentId/');

export function IncidentPage() {
  const params = route.useParams();
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
          {incident.external_links.slack ? (
            <SlackLink
              slackUrl={incident.external_links.slack}
              incidentId={params.incidentId}
            />
          ) : null}
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
