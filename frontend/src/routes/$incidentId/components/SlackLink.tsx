import {Card} from 'components/Card';

interface SlackLinkProps {
  slackUrl: string;
  incidentId: string;
}

export function SlackLink({slackUrl, incidentId}: SlackLinkProps) {
  return (
    <a href={slackUrl} target="_blank" rel="noopener noreferrer" className="block">
      <Card className="hover:bg-background-transparent-neutral-muted cursor-pointer transition-colors duration-200">
        <div className="flex items-center gap-3">
          <img src="/slack-icon.svg" alt="Slack" className="h-7 w-7" />
          <span className="text-content-headings text-base font-semibold">
            Join #{incidentId.toLowerCase()}
          </span>
        </div>
      </Card>
    </a>
  );
}
