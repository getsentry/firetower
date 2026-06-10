import {Suspense, useState} from 'react';
import {useMutation, useQueryClient, useSuspenseQuery} from '@tanstack/react-query';
import {CatchBoundary} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {buttonVariants} from 'components/Button';
import {Card} from 'components/Card';
import {ConfirmationDialog} from 'components/ConfirmationDialog';
import {GetHelpLink} from 'components/GetHelpLink';
import {Pill} from 'components/Pill';
import {Skeleton} from 'components/Skeleton';
import {Loader2, Plus, RefreshCw} from 'lucide-react';
import {cn} from 'utils/cn';

import type {ActionItem, ActionItemStatus} from '../queries/actionItemsQueryOptions';
import {actionItemsQueryOptions} from '../queries/actionItemsQueryOptions';
import {syncActionItemsMutationOptions} from '../queries/syncActionItemsMutationOptions';

import {PriorityIcon} from './PriorityIcon';

const BORDER_CLASS: Record<ActionItemStatus, string> = {
  Done: 'border-success-vibrant',
  'In Progress': 'border-warning-vibrant',
  Todo: 'border-neutral-muted',
  Canceled: 'border-neutral-muted',
};

function ActionItemCard({item}: {item: ActionItem}) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'flex items-center gap-space-lg rounded-radius-md border-l-4 p-space-lg no-underline transition-colors duration-200',
        'hover:bg-background-transparent-neutral-muted',
        BORDER_CLASS[item.status]
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="text-content-headings text-sm font-medium">{item.title}</p>
        <div className="text-content-secondary mt-space-xs gap-space-sm flex items-center text-xs">
          <span>{item.linear_identifier}</span>
          {item.assignee_name ? (
            <>
              <span aria-hidden="true">&middot;</span>
              <span className="gap-space-xs flex items-center">
                <Avatar
                  name={item.assignee_name}
                  src={item.assignee_avatar_url}
                  size="sm"
                  className="!h-4 !w-4 !text-[10px]"
                />
                {item.assignee_name}
              </span>
            </>
          ) : null}
        </div>
      </div>
      <PriorityIcon priority={item.priority} />
      <Pill variant={item.status}>{item.status}</Pill>
    </a>
  );
}

function buildLinearCreateUrl(linearUrl: string, parentIssueId: string): string | null {
  try {
    const url = new URL(linearUrl);
    const workspace = url.pathname.split('/')[1];
    if (!workspace) return null;
    return `https://linear.app/${workspace}/new?parentId=${parentIssueId}`;
  } catch {
    return null;
  }
}

interface ActionItemsListProps {
  incidentId: string;
  linearUrl?: string;
  linearParentIssueId?: string | null;
}

export function ActionItemsList({
  incidentId,
  linearUrl,
  linearParentIssueId,
}: ActionItemsListProps) {
  const queryClient = useQueryClient();
  const syncMutation = useMutation(
    syncActionItemsMutationOptions(queryClient, incidentId)
  );
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <h2 className="text-content-headings text-lg font-semibold">Action Items</h2>
        <div className="gap-space-sm flex items-center">
          <button
            type="button"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className={cn(buttonVariants({variant: 'icon'}))}
            aria-label="Sync action items"
          >
            {syncMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </button>
          {linearUrl ? (
            <button
              type="button"
              onClick={() => setShowCreateDialog(true)}
              className={cn(buttonVariants({variant: 'icon'}))}
              aria-label="Create action item"
            >
              <Plus className="h-4 w-4" strokeWidth={3} />
            </button>
          ) : null}
        </div>
      </div>
      {syncMutation.isError ? (
        <p className="text-content-danger mb-space-md text-sm">
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
              You'll be taken to Linear to create a sub-issue under the parent incident
              issue.
              <br />
              <br />
              Make sure to assign the issue to the appropriate team as issues in the
              Incident Management team will be overwritten by Firetower.
              <br />
              <br />
              Please set priority on the issues according to our policy:
              <ul
                className="mt-space-xs space-y-space-xs text-sm"
                style={{listStyle: 'none', paddingLeft: 0}}
              >
                <li className="gap-space-xs flex flex-wrap items-center">
                  <PriorityIcon priority={1} /> <strong>Urgent</strong> /{' '}
                  <PriorityIcon priority={2} /> <strong>High (P1)</strong> — 2 week SLA
                </li>
                <li className="gap-space-xs flex flex-wrap items-center">
                  <PriorityIcon priority={3} /> <strong>Medium (P2)</strong> — 4 week SLA
                </li>
                <li className="gap-space-xs flex flex-wrap items-center">
                  <PriorityIcon priority={4} /> <strong>Low (P3)</strong> — no SLA, can be
                  put on backlog
                </li>
              </ul>
            </>
          }
          confirmLabel="Create in Linear"
          onConfirm={() => {
            const createUrl =
              linearParentIssueId && buildLinearCreateUrl(linearUrl, linearParentIssueId);
            window.open(createUrl || linearUrl, '_blank', 'noopener,noreferrer');
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
    <p className="text-content-secondary text-center text-sm">
      This incident has no linked Linear issue, try refreshing to generate a new Linear
      issue. If the problem persists, come let us know in <GetHelpLink />.
    </p>
  );
}

function ActionItemsError() {
  return (
    <p className="text-content-secondary text-center text-sm">
      Failed to load action items. Try refreshing, or come let us know in <GetHelpLink />.
    </p>
  );
}

function ActionItemsBodySkeleton() {
  return (
    <div className="gap-space-md flex flex-col">
      <Skeleton className="rounded-radius-md h-16 w-full" />
      <Skeleton className="rounded-radius-md h-16 w-full" />
      <Skeleton className="rounded-radius-md h-16 w-full" />
    </div>
  );
}

function ActionItemsLinked({incidentId}: {incidentId: string}) {
  const {data: actionItems} = useSuspenseQuery(actionItemsQueryOptions({incidentId}));

  return actionItems.length === 0 ? (
    <p className="text-content-secondary text-center text-sm">Nothing here yet</p>
  ) : (
    <div className="gap-space-md flex flex-col">
      {actionItems.map(item => (
        <ActionItemCard key={item.linear_identifier} item={item} />
      ))}
    </div>
  );
}
