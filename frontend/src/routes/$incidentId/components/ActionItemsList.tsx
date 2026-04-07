import {Avatar} from 'components/Avatar';
import {buttonVariants} from 'components/Button';
import {Card} from 'components/Card';
import {Pill} from 'components/Pill';
import {Plus} from 'lucide-react';
import {cn} from 'utils/cn';

import type {ActionItem, ActionItemStatus} from '../queries/incidentDetailQueryOptions';

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

function buildLinearNewUrl(incidentId: string, incidentTitle: string): string {
  const firetowerUrl = `${window.location.origin}/${incidentId}/`;
  const params = new URLSearchParams({
    'attachment[url]': firetowerUrl,
    'attachment[title]': incidentTitle,
  });
  return `https://linear.app/new?${params.toString()}`;
}

interface ActionItemsListProps {
  incidentId: string;
  incidentTitle: string;
  actionItems: ActionItem[];
}

export function ActionItemsList({
  incidentId,
  incidentTitle,
  actionItems,
}: ActionItemsListProps) {
  return (
    <Card>
      <div className="mb-space-lg flex items-center justify-between">
        <h2 className="text-content-headings text-lg font-semibold">Action Items</h2>
        <a
          href={buildLinearNewUrl(incidentId, incidentTitle)}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(buttonVariants({variant: 'icon'}))}
          aria-label="Create Linear issue"
        >
          <Plus className="h-4 w-4" />
        </a>
      </div>
      {actionItems.length === 0 ? (
        <p className="text-content-secondary text-sm">No action items yet</p>
      ) : (
        <div className="gap-space-md flex flex-col">
          {actionItems.map(item => (
            <ActionItemCard key={item.linear_identifier} item={item} />
          ))}
        </div>
      )}
    </Card>
  );
}
