import {Card} from 'components/Card';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

const linkConfigs = {
  datadog: {
    label: 'Datadog',
    icon: '/datadog.svg',
  },
  jira: {
    label: 'Jira',
    icon: '/jira.svg',
  },
  linear: {
    label: 'Linear',
    icon: '/linear.svg',
  },
  notion: {
    label: 'Notion',
    icon: '/notion.svg',
  },
  pagerduty: {
    label: 'PagerDuty',
    icon: '/pagerduty.svg',
  },
  statuspage: {
    label: 'Statuspage',
    icon: '/statuspage.svg',
  },
} as const;

type LinkType = keyof typeof linkConfigs;

interface LinkProps {
  type: LinkType;
  url: string;
  isLast?: boolean;
}

function Link({type, url, isLast = false}: LinkProps) {
  const config = linkConfigs[type];

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-content-accent py-space-lg hover:text-content-accent/80 flex items-center gap-3 no-underline transition-colors ${
        !isLast ? 'border-b border-gray-200' : ''
      }`}
    >
      <img src={config.icon} alt={config.label} className="h-[18px] w-[18px]" />
      <span>{config.label}</span>
    </a>
  );
}

interface LinksListProps {
  externalLinks: IncidentDetail['external_links'];
}

export function LinksList({externalLinks}: LinksListProps) {
  const linkTypes = Object.keys(linkConfigs) as LinkType[];
  const visibleLinks = linkTypes.filter(type => externalLinks[type]);

  if (visibleLinks.length === 0) {
    return null;
  }

  return (
    <Card>
      <div className="flex flex-col">
        {linkTypes.map(type => {
          const url = externalLinks[type];
          if (!url) return null;

          const isLast = type === visibleLinks[visibleLinks.length - 1];

          return <Link key={type} type={type} url={url} isLast={isLast} />;
        })}
      </div>
    </Card>
  );
}
