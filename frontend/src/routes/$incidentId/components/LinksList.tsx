import {Card} from 'components/Card';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

const linkConfigs = {
  datadog: {
    label: 'Datadog notebook',
    icon: '/datadog.svg',
  },
  linear: {
    label: 'Linear',
    icon: '/linear.svg',
  },
  notion: {
    label: 'Postmortem document',
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
}

function Link({type, url}: LinkProps) {
  const config = linkConfigs[type];

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-content-accent py-space-lg hover:text-content-accent/80 flex items-center gap-3 no-underline transition-colors"
    >
      <img
        src={config.icon}
        alt={config.label}
        className="h-[18px] w-[18px] dark:invert"
      />
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

          return <Link key={type} type={type} url={url} />;
        })}
      </div>
    </Card>
  );
}
