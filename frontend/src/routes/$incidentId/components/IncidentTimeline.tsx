import {Suspense} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useSuspenseQuery} from '@tanstack/react-query';
import {CatchBoundary} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';
import {Skeleton} from 'components/Skeleton';
import {Activity, Radio, Siren, UserRound, type LucideIcon} from 'lucide-react';

import {background, content, fontWeight, space} from '../../../styles/tokens.stylex';
import type {
  TimelineEvent,
  TimelineEventSource,
} from '../queries/incidentTimelineQueryOptions';
import {incidentTimelineQueryOptions} from '../queries/incidentTimelineQueryOptions';

const styles = stylex.create({
  row: {
    paddingBottom: {default: space.xl, ':last-child': '0px'},
    gap: space.md,
    position: 'relative',
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
  },
  icon: {height: '16px', width: '16px'},
  connector: {
    backgroundColor: background.secondary,
    position: 'absolute',
    top: '28px',
    bottom: '0px',
    left: '14px',
    width: '1px',
  },
  body: {minWidth: '0px'},
  summary: {
    color: content.headings,
    fontSize: '14px',
    lineHeight: '20px',
    fontWeight: fontWeight.medium,
  },
  metadata: {
    color: content.secondary,
    marginTop: space.xs,
    gap: space.sm,
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    fontSize: '12px',
    lineHeight: '16px',
  },
  actor: {gap: space.xs, display: 'flex', alignItems: 'center'},
  avatar: {height: '20px', width: '20px', fontSize: '10px'},
  sourceLink: {
    color: content.accent,
    textDecoration: {default: null, ':hover': 'underline'},
  },
  empty: {
    color: content.secondary,
    textAlign: 'center',
    fontSize: '14px',
    lineHeight: '20px',
  },
  loading: {gap: space.xl, display: 'flex', flexDirection: 'column'},
  screenReader: {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    borderWidth: 0,
  },
  loadingRow: {gap: space.md, display: 'flex', alignItems: 'flex-start'},
  loadingIcon: {height: '28px', width: '28px', flexShrink: 0, borderRadius: '9999px'},
  loadingText: {gap: space.sm, display: 'flex', flex: '1 1 0%', flexDirection: 'column'},
  loadingTitle: {height: '16px', width: '75%'},
  loadingMetadata: {height: '12px', width: '50%'},
  error: {
    color: content.danger,
    textAlign: 'center',
    fontSize: '14px',
    lineHeight: '20px',
  },
  heading: {
    color: content.headings,
    marginBottom: space.lg,
    fontSize: '18px',
    lineHeight: '28px',
    fontWeight: 600,
  },
  sourceIcon: {
    zIndex: 10,
    display: 'flex',
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '9999px',
  },
  sourceNeutral: {backgroundColor: background.secondary, color: content.secondary},
  sourceWarning: {
    backgroundColor: background.transparentWarningMuted,
    color: content.warning,
  },
  sourceDanger: {
    backgroundColor: background.transparentDangerMuted,
    color: content.danger,
  },
  lastConnector: {display: 'none'},
});

interface SourceStyle {
  label: string;
  Icon: LucideIcon;
  style: stylex.StyleXStyles;
}

const SOURCE_STYLES: Record<TimelineEventSource, SourceStyle> = {
  USER: {
    label: 'User',
    Icon: UserRound,
    style: styles.sourceNeutral,
  },
  INTERNAL: {
    label: 'Firetower',
    Icon: Activity,
    style: styles.sourceNeutral,
  },
  STATUSPAGE: {
    label: 'Statuspage',
    Icon: Radio,
    style: styles.sourceWarning,
  },
  PAGERDUTY: {
    label: 'PagerDuty',
    Icon: Siren,
    style: styles.sourceDanger,
  },
};

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  });
}

function TimelineRow({event, isLast}: {event: TimelineEvent; isLast: boolean}) {
  const sourceStyle = SOURCE_STYLES[event.source];
  const SourceIcon = sourceStyle.Icon;

  return (
    <li {...stylex.props(styles.row)}>
      <div {...stylex.props(styles.sourceIcon, sourceStyle.style)}>
        <SourceIcon {...stylex.props(styles.icon)} aria-hidden="true" />
      </div>
      <span
        {...stylex.props(styles.connector, isLast && styles.lastConnector)}
        aria-hidden="true"
      />
      <div {...stylex.props(styles.body)}>
        <p {...stylex.props(styles.summary)}>{event.summary}</p>
        <div {...stylex.props(styles.metadata)}>
          {event.actor ? (
            <span {...stylex.props(styles.actor)}>
              <span aria-hidden="true">
                <Avatar
                  name={event.actor.name}
                  src={event.actor.avatar_url}
                  size="sm"
                  style={styles.avatar}
                />
              </span>
              {event.actor.name}
            </span>
          ) : (
            <span>{sourceStyle.label}</span>
          )}
          <span aria-hidden="true">&middot;</span>
          <time dateTime={event.occurred_at}>{formatDateTime(event.occurred_at)}</time>
          {event.link_url ? (
            <>
              <span aria-hidden="true">&middot;</span>
              <a
                href={event.link_url}
                target="_blank"
                rel="noopener noreferrer"
                {...stylex.props(styles.sourceLink)}
              >
                View source
              </a>
            </>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function TimelineBody({incidentId}: {incidentId: string}) {
  const {data: events} = useSuspenseQuery(incidentTimelineQueryOptions({incidentId}));

  return events.length === 0 ? (
    <p {...stylex.props(styles.empty)}>No timeline events yet.</p>
  ) : (
    <ol>
      {events.map((event, index) => (
        <TimelineRow key={event.id} event={event} isLast={index === events.length - 1} />
      ))}
    </ol>
  );
}

function TimelineLoading() {
  return (
    <div {...stylex.props(styles.loading)} role="status" aria-label="Loading timeline">
      <span {...stylex.props(styles.screenReader)}>Loading timeline</span>
      {[0, 1, 2].map(index => (
        <div
          key={index}
          {...stylex.props(styles.loadingRow)}
          data-testid="timeline-skeleton-row"
        >
          <Skeleton style={styles.loadingIcon} />
          <div {...stylex.props(styles.loadingText)}>
            <Skeleton style={styles.loadingTitle} />
            <Skeleton style={styles.loadingMetadata} />
          </div>
        </div>
      ))}
    </div>
  );
}

function TimelineError() {
  return (
    <p {...stylex.props(styles.error)} role="alert">
      Failed to load timeline events. Please try again.
    </p>
  );
}

export function IncidentTimeline({incidentId}: {incidentId: string}) {
  const headingId = `incident-${incidentId}-timeline-heading`;

  return (
    <Card>
      <section aria-labelledby={headingId}>
        <h2 id={headingId} {...stylex.props(styles.heading)}>
          Timeline
        </h2>
        <CatchBoundary getResetKey={() => incidentId} errorComponent={TimelineError}>
          <Suspense fallback={<TimelineLoading />}>
            <TimelineBody incidentId={incidentId} />
          </Suspense>
        </CatchBoundary>
      </section>
    </Card>
  );
}
