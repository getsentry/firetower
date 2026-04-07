import {useQuery} from '@tanstack/react-query';
import {Avatar} from 'components/Avatar';
import {Card} from 'components/Card';
import {Pill} from 'components/Pill';
import {cn} from 'utils/cn';

import type {ActionItem, ActionItemStatus} from '../queries/actionItemsQueryOptions';
import {actionItemsQueryOptions} from '../queries/actionItemsQueryOptions';

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

interface ActionItemsListProps {
  incidentId: string;
}

export function ActionItemsList({incidentId}: ActionItemsListProps) {
  const {data: actionItems} = useQuery(actionItemsQueryOptions({incidentId}));

  if (!actionItems || actionItems.length === 0) {
    return null;
  }

  return (
    <Card>
      <Card.Title>Action Items</Card.Title>
      <div className="gap-space-md flex flex-col">
        {actionItems.map(item => (
          <ActionItemCard key={item.linear_identifier} item={item} />
        ))}
      </div>
    </Card>
  );
}
