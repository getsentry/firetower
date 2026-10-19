import {Suspense} from 'react';
import {useSuspenseQuery} from '@tanstack/react-query';
import {CatchBoundary} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';
import {Skeleton} from 'components/Skeleton';
import {Activity, Radio, Siren, UserRound, type LucideIcon} from 'lucide-react';

import type {
  TimelineEvent,
  TimelineEventSource,
} from '../queries/incidentTimelineQueryOptions';
import {incidentTimelineQueryOptions} from '../queries/incidentTimelineQueryOptions';

interface SourceStyle {
  label: string;
  Icon: LucideIcon;
  iconClassName: string;
}

const SOURCE_STYLES: Record<TimelineEventSource, SourceStyle> = {
  USER: {
    label: 'User',
    Icon: UserRound,
    iconClassName: 'bg-background-secondary text-content-secondary',
  },
  INTERNAL: {
    label: 'Firetower',
    Icon: Activity,
    iconClassName: 'bg-background-secondary text-content-secondary',
  },
  STATUSPAGE: {
    label: 'Statuspage',
    Icon: Radio,
    iconClassName: 'bg-background-transparent-warning-muted text-content-warning',
  },
  PAGERDUTY: {
    label: 'PagerDuty',
    Icon: Siren,
    iconClassName: 'bg-background-transparent-danger-muted text-content-danger',
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

function TimelineRow({event}: {event: TimelineEvent}) {
  const sourceStyle = SOURCE_STYLES[event.source];
  const SourceIcon = sourceStyle.Icon;

  return (
    <li className="group pb-space-xl gap-space-md relative grid grid-cols-[auto_1fr] last:pb-0">
      <div
        className={`z-10 flex h-7 w-7 items-center justify-center rounded-full ${sourceStyle.iconClassName}`}
      >
        <SourceIcon className="h-4 w-4" aria-hidden="true" />
      </div>
      <span
        className="bg-background-secondary absolute top-7 bottom-0 left-3.5 w-px group-last:hidden"
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="text-content-headings text-sm font-medium">{event.summary}</p>
        <div className="text-content-secondary mt-space-xs gap-space-sm flex flex-wrap items-center text-xs">
          {event.actor ? (
            <span className="gap-space-xs flex items-center">
              <span aria-hidden="true">
                <Avatar
                  name={event.actor.name}
                  src={event.actor.avatar_url}
                  size="sm"
                  className="!h-5 !w-5 !text-[10px]"
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
                className="text-content-accent hover:underline"
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
    <p className="text-content-secondary text-center text-sm">No timeline events yet.</p>
  ) : (
    <ol>
      {events.map(event => (
        <TimelineRow key={event.id} event={event} />
      ))}
    </ol>
  );
}

function TimelineLoading() {
  return (
    <div
      className="gap-space-xl flex flex-col"
      role="status"
      aria-label="Loading timeline"
    >
      <span className="sr-only">Loading timeline</span>
      {[0, 1, 2].map(index => (
        <div
          key={index}
          className="gap-space-md flex items-start"
          data-testid="timeline-skeleton-row"
        >
          <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
          <div className="gap-space-sm flex flex-1 flex-col">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

function TimelineError() {
  return (
    <p className="text-content-danger text-center text-sm" role="alert">
      Failed to load timeline events. Please try again.
    </p>
  );
}

export function IncidentTimeline({incidentId}: {incidentId: string}) {
  const headingId = `incident-${incidentId}-timeline-heading`;

  return (
    <Card>
      <section aria-labelledby={headingId}>
        <h2
          id={headingId}
          className="text-content-headings mb-space-lg text-lg font-semibold"
        >
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
