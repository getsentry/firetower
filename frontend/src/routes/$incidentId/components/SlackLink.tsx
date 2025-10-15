import {Card} from 'components/Card';

interface SlackLinkProps {
  slackUrl: string;
  incidentId: string;
}

export function SlackLink({slackUrl, incidentId}: SlackLinkProps) {
  return (
    <a href={slackUrl} target="_blank" rel="noopener noreferrer" className="block">
      <Card className="cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg">
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
