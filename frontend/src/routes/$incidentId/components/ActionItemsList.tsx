import {useMutation, useQueryClient, useSuspenseQuery} from '@tanstack/react-query';
import {Avatar} from 'components/Avatar';
import {buttonVariants} from 'components/Button';
import {Card} from 'components/Card';
import {GetHelpLink} from 'components/GetHelpLink';
import {Pill} from 'components/Pill';
import {Loader2, Plus, RefreshCw} from 'lucide-react';
import {cn} from 'utils/cn';

import type {ActionItem, ActionItemStatus} from '../queries/actionItemsQueryOptions';
import {actionItemsQueryOptions} from '../queries/actionItemsQueryOptions';
import {syncActionItemsMutationOptions} from '../queries/syncActionItemsMutationOptions';

const STATUS_CONFIG: Record<
  ActionItemStatus,
  {pillVariant: 'Done' | 'Mitigated' | 'Active' | 'Cancelled'; borderClass: string}
> = {
  Done: {pillVariant: 'Done', borderClass: 'border-success-vibrant'},
  'In Progress': {pillVariant: 'Mitigated', borderClass: 'border-warning-vibrant'},
  Todo: {pillVariant: 'Active', borderClass: 'border-danger-vibrant'},
  Cancelled: {pillVariant: 'Cancelled', borderClass: 'border-neutral-muted'},
};

function ActionItemCard({item}: {item: ActionItem}) {
  const config = STATUS_CONFIG[item.status];

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(
        'flex items-center gap-space-lg rounded-radius-md border-l-4 bg-background-secondary p-space-lg no-underline transition-colors',
        'hover:bg-background-tertiary',
        config.borderClass
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="text-content-headings text-sm font-medium">{item.title}</p>
        <div className="text-content-secondary mt-space-xs gap-space-sm flex items-center text-xs">
          <span>{item.linear_identifier}</span>
          {item.assignee_name && (
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
          )}
        </div>
      </div>
      <Pill variant={config.pillVariant}>{item.status}</Pill>
    </a>
  );
}

function extractLinearIdentifier(linearUrl: string): string | null {
  const match = linearUrl.match(/\/issue\/([A-Z]+-\d+)/);
  return match ? match[1] : null;
}

function buildLinearNewUrl(linearUrl: string): string | null {
  const identifier = extractLinearIdentifier(linearUrl);
  if (!identifier) {
    return null;
  }
  const params = new URLSearchParams({parent: identifier});
  return `https://linear.app/new?${params.toString()}`;
}

interface ActionItemsListProps {
  incidentId: string;
  linearUrl?: string;
}

export function ActionItemsList({incidentId, linearUrl}: ActionItemsListProps) {
  const createUrl = linearUrl ? buildLinearNewUrl(linearUrl) : null;
  const queryClient = useQueryClient();
  const syncMutation = useMutation(
    syncActionItemsMutationOptions(queryClient, incidentId)
  );

  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <h2 className="text-content-headings text-lg font-semibold">Action Items</h2>
        <div className="flex items-center gap-space-sm">
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
          {createUrl ? (
            <a
              href={createUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(buttonVariants({variant: 'icon'}))}
              aria-label="Create Linear issue"
            >
              <Plus className="h-4 w-4" />
            </a>
          ) : null}
        </div>
      </div>
      {linearUrl ? <ActionItemsLinked incidentId={incidentId} /> : <ActionItemsEmpty />}
    </Card>
  );
}

function ActionItemsEmpty() {
  return (
    <p className="text-content-secondary text-sm">
      This incident has no linked Linear issue, try refreshing to generate a new Linear
      issue. If the problem persists, come let us know in <GetHelpLink />.
    </p>
  );
}

function ActionItemsLinked({incidentId}: {incidentId: string}) {
  const {data: actionItems} = useSuspenseQuery(actionItemsQueryOptions({incidentId}));

  return actionItems.length === 0 ? (
    <p className="text-content-secondary text-sm">No action items yet</p>
  ) : (
    <div className="gap-space-md flex flex-col">
      {actionItems.map(item => (
        <ActionItemCard key={item.linear_identifier} item={item} />
      ))}
    </div>
  );
}
