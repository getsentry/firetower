import {Card} from 'components/Card';

interface SlackLinkProps {
  slackUrl: string;
  incidentId: string;
}

export function SlackLink({slackUrl, incidentId}: SlackLinkProps) {
  return (
    <a href={slackUrl} target="_blank" rel="noopener noreferrer" className="block">
      <Card className="hover:shadow-lg transition-all duration-200 hover:-translate-y-0.5 cursor-pointer">
        <div className="flex items-center gap-3">
          <img src="/slack-icon.svg" alt="Slack" className="w-7 h-7" />
          <span className="text-base font-semibold text-content-headings">
            Join #{incidentId.toLowerCase()}
          </span>
        </div>
      </Card>
    </a>
  );
}
