import * as stylex from '@stylexjs/stylex';
import {Card} from 'components/Card';

import {content, space} from '../../../styles/tokens.stylex';
import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

const linkConfigs = {
  datadog: {
    label: 'Datadog notebook',
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
    label: 'Postmortem document',
    icon: '/notion.svg',
  },
  notion_troubleshooting: {
    label: 'Troubleshooting document',
    icon: '/notion.svg',
  },
  pagerduty: {
    label: 'PagerDuty',
    icon: '/pagerduty.svg',
  },
  postmortem_meeting: {
    label: 'Postmortem meeting',
    icon: '/postmortem_meeting.svg',
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
      {...stylex.props(styles.link)}
    >
      <img src={config.icon} alt={config.label} {...stylex.props(styles.icon)} />
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
      <div {...stylex.props(styles.list)}>
        {linkTypes.map(type => {
          const url = externalLinks[type];
          if (!url) return null;

          return <Link key={type} type={type} url={url} />;
        })}
      </div>
    </Card>
  );
}

const styles = stylex.create({
  link: {
    color: {
      default: content.accent,
      ':hover': `color-mix(in srgb, ${content.accent} 80%, transparent)`,
    },
    paddingTop: space.lg,
    paddingBottom: space.lg,
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    textDecoration: 'none',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  icon: {
    height: '18px',
    width: '18px',
    filter: {default: null, '@media (prefers-color-scheme: dark)': 'invert(100%)'},
  },
  list: {display: 'flex', flexDirection: 'column'},
});
