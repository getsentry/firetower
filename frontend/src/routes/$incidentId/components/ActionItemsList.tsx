import {Suspense, useState} from 'react';
import * as stylex from '@stylexjs/stylex';
import {useMutation, useQueryClient, useSuspenseQuery} from '@tanstack/react-query';
import {CatchBoundary} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {Button} from 'components/Button';
import {Card} from 'components/Card';
import {ConfirmationDialog} from 'components/ConfirmationDialog';
import {GetHelpLink} from 'components/GetHelpLink';
import {Pill} from 'components/Pill';
import {Skeleton} from 'components/Skeleton';
import {Loader2, Plus, RefreshCw} from 'lucide-react';

import {
  background,
  border,
  content,
  fontWeight,
  radius,
  space,
} from '../../../styles/tokens.stylex';
import type {ActionItem, ActionItemStatus} from '../queries/actionItemsQueryOptions';
import {actionItemsQueryOptions} from '../queries/actionItemsQueryOptions';
import {syncActionItemsMutationOptions} from '../queries/syncActionItemsMutationOptions';

import {PriorityIcon} from './PriorityIcon';

function getSloLabel(
  deadline: string
): {text: string; tone: 'danger' | 'warning' | 'secondary'} | null {
  const now = new Date();
  const due = new Date(deadline);
  const diffMs = due.getTime() - now.getTime();
  const msPerDay = 1000 * 60 * 60 * 24;

  if (diffMs < 0) {
    const overdueDays = Math.floor(Math.abs(diffMs) / msPerDay);
    return {
      text: `${overdueDays}d overdue`,
      tone: 'danger',
    };
  }
  const diffDays = Math.floor(diffMs / msPerDay);
  if (diffDays <= 3) {
    return {
      text: `${diffDays}d left`,
      tone: 'warning',
    };
  }
  return {
    text: `${diffDays}d left`,
    tone: 'secondary',
  };
}

function ActionItemCard({item}: {item: ActionItem}) {
  const isTerminal = item.status === 'Done' || item.status === 'Canceled';
  const slo = item.slo_deadline && !isTerminal ? getSloLabel(item.slo_deadline) : null;

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      {...stylex.props(styles.item)}
    >
      <div
        aria-hidden="true"
        {...stylex.props(styles.statusBorder, statusStyles[item.status])}
      />
      <div {...stylex.props(styles.body)}>
        <p {...stylex.props(styles.title)}>{item.title}</p>
        <div {...stylex.props(styles.metadata)}>
          <span>{item.linear_identifier}</span>
          {item.assignee_name ? (
            <>
              <span aria-hidden="true">&middot;</span>
              <span {...stylex.props(styles.assignee)}>
                <Avatar
                  name={item.assignee_name}
                  src={item.assignee_avatar_url}
                  size="sm"
                  style={styles.avatar}
                />
                {item.assignee_name}
              </span>
            </>
          ) : null}
          {slo ? (
            <>
              <span aria-hidden="true">&middot;</span>
              <span {...stylex.props(sloStyles[slo.tone])}>{slo.text}</span>
            </>
          ) : null}
        </div>
      </div>
      <PriorityIcon priority={item.priority} />
      <Pill variant={item.status}>{item.status}</Pill>
    </a>
  );
}

interface ActionItemsListProps {
  incidentId: string;
  linearUrl?: string;
}

export function ActionItemsList({incidentId, linearUrl}: ActionItemsListProps) {
  const queryClient = useQueryClient();
  const syncMutation = useMutation(
    syncActionItemsMutationOptions(queryClient, incidentId)
  );
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  return (
    <Card>
      <div {...stylex.props(styles.header)}>
        <h2 {...stylex.props(styles.heading)}>Action Items</h2>
        <div {...stylex.props(styles.actions)}>
          <Button
            variant="icon"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            aria-label="Sync action items"
          >
            {syncMutation.isPending ? (
              <Loader2 {...stylex.props(styles.spinningIcon)} />
            ) : (
              <RefreshCw {...stylex.props(styles.icon)} />
            )}
          </Button>
          {linearUrl ? (
            <Button
              variant="icon"
              onClick={() => setShowCreateDialog(true)}
              aria-label="Create action item"
            >
              <Plus {...stylex.props(styles.icon)} strokeWidth={3} />
            </Button>
          ) : null}
        </div>
      </div>
      {syncMutation.isError ? (
        <p {...stylex.props(styles.error)}>
          Failed to sync action items. Please try again.
        </p>
      ) : null}
      {linearUrl ? (
        <CatchBoundary
          getResetKey={() => `${incidentId}:${syncMutation.submittedAt}`}
          errorComponent={ActionItemsError}
        >
          <Suspense fallback={<ActionItemsBodySkeleton />}>
            <ActionItemsLinked incidentId={incidentId} />
          </Suspense>
        </CatchBoundary>
      ) : (
        <ActionItemsEmpty />
      )}
      {linearUrl ? (
        <ConfirmationDialog
          isOpen={showCreateDialog}
          title="Create Action Item"
          message={
            <>
              You'll be taken to the parent Linear issue for the incident. Create your
              action item as a sub-issue or related issue there.
              <br />
              <br />
              Make sure to assign the issue to the appropriate team as issues in the
              Incident Management team will be overwritten by Firetower.
              <br />
              <br />
              Please set priority on the issues according to our policy:
              <ul {...stylex.props(styles.priorities)}>
                <li {...stylex.props(styles.priority)}>
                  <PriorityIcon priority={1} /> <strong>Urgent</strong> /{' '}
                  <PriorityIcon priority={2} /> <strong>High (P1)</strong> — 2 week SLA
                </li>
                <li {...stylex.props(styles.priority)}>
                  <PriorityIcon priority={3} /> <strong>Medium (P2)</strong> — 4 week SLA
                </li>
                <li {...stylex.props(styles.priority)}>
                  <PriorityIcon priority={4} /> <strong>Low (P3)</strong> — no SLA, can be
                  put on backlog
                </li>
              </ul>
            </>
          }
          confirmLabel="Open Linear"
          onConfirm={() => {
            window.open(linearUrl, '_blank', 'noopener,noreferrer');
            setShowCreateDialog(false);
          }}
          onCancel={() => setShowCreateDialog(false)}
        />
      ) : null}
    </Card>
  );
}

function ActionItemsEmpty() {
  return (
    <p {...stylex.props(styles.empty)}>
      This incident has no linked Linear issue, try refreshing to generate a new Linear
      issue. If the problem persists, come let us know in <GetHelpLink />.
    </p>
  );
}

function ActionItemsError() {
  return (
    <p {...stylex.props(styles.empty)}>
      Failed to load action items. Try refreshing, or come let us know in <GetHelpLink />.
    </p>
  );
}

function ActionItemsBodySkeleton() {
  return (
    <div {...stylex.props(styles.loading)}>
      <Skeleton style={styles.skeleton} />
      <Skeleton style={styles.skeleton} />
      <Skeleton style={styles.skeleton} />
    </div>
  );
}

function ActionItemsLinked({incidentId}: {incidentId: string}) {
  const {data: actionItems} = useSuspenseQuery(actionItemsQueryOptions({incidentId}));

  return actionItems.length === 0 ? (
    <p {...stylex.props(styles.empty)}>Nothing here yet</p>
  ) : (
    <div {...stylex.props(styles.loading)}>
      {actionItems.map(item => (
        <ActionItemCard key={item.linear_identifier} item={item} />
      ))}
    </div>
  );
}

const styles = stylex.create({
  item: {
    gap: space.lg,
    borderRadius: radius.md,
    padding: space.lg,
    backgroundColor: {default: null, ':hover': background.transparentNeutralMuted},
    position: 'relative',
    display: 'flex',
    cursor: 'pointer',
    alignItems: 'center',
    textDecoration: 'none',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '200ms',
  },
  body: {minWidth: '0px', flex: '1 1 0%'},
  title: {
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
    alignItems: 'center',
    fontSize: '12px',
    lineHeight: '16px',
  },
  assignee: {gap: space.xs, display: 'flex', alignItems: 'center'},
  avatar: {height: '16px', width: '16px', fontSize: '10px'},
  header: {
    marginBottom: space.lg,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heading: {
    color: content.headings,
    fontSize: '18px',
    lineHeight: '28px',
    fontWeight: 600,
  },
  actions: {gap: space.sm, display: 'flex', alignItems: 'center'},
  spinningIcon: {
    height: '16px',
    width: '16px',
    animationName: stylex.keyframes({
      from: {transform: 'rotate(0deg)'},
      to: {transform: 'rotate(360deg)'},
    }),
    animationDuration: '1s',
    animationTimingFunction: 'linear',
    animationIterationCount: 'infinite',
  },
  icon: {height: '16px', width: '16px'},
  error: {
    color: content.danger,
    marginBottom: space.md,
    fontSize: '14px',
    lineHeight: '20px',
  },
  priorities: {
    listStyleType: 'none',
    paddingLeft: 0,
    marginTop: space.xs,
    display: 'flex',
    flexDirection: 'column',
    rowGap: space.xs,
    fontSize: '14px',
    lineHeight: '20px',
  },
  priority: {gap: space.xs, display: 'flex', flexWrap: 'wrap', alignItems: 'center'},
  empty: {
    color: content.secondary,
    textAlign: 'center',
    fontSize: '14px',
    lineHeight: '20px',
  },
  loading: {gap: space.md, display: 'flex', flexDirection: 'column'},
  skeleton: {borderRadius: radius.md, height: '64px', width: '100%'},
  statusBorder: {
    pointerEvents: 'none',
    position: 'absolute',
    top: 4,
    bottom: 4,
    left: 2,
    borderRadius: radius.md,
    borderLeftWidth: 4,
    borderLeftStyle: 'solid',
  },
  statusDone: {borderColor: border.successVibrant},
  statusInProgress: {borderColor: border.warningVibrant},
  statusInactive: {borderColor: border.neutralMuted},
  sloDanger: {color: content.danger},
  sloWarning: {color: content.warning},
  sloSecondary: {color: content.secondary},
});

const statusStyles: Record<ActionItemStatus, stylex.StyleXStyles> = {
  Done: styles.statusDone,
  'In Progress': styles.statusInProgress,
  Todo: styles.statusInactive,
  Canceled: styles.statusInactive,
};
const sloStyles = {
  danger: styles.sloDanger,
  warning: styles.sloWarning,
  secondary: styles.sloSecondary,
};
