import * as stylex from '@stylexjs/stylex';
import {Card} from 'components/Card';

import {background, content} from '../../../styles/tokens.stylex';

interface SlackLinkProps {
  slackUrl: string;
  incidentId: string;
}

export function SlackLink({slackUrl, incidentId}: SlackLinkProps) {
  return (
    <a
      href={slackUrl}
      target="_blank"
      rel="noopener noreferrer"
      {...stylex.props(styles.link)}
    >
      <Card style={styles.card}>
        <div {...stylex.props(styles.content)}>
          <img src="/slack-icon.svg" alt="Slack" {...stylex.props(styles.icon)} />
          <span {...stylex.props(styles.label)}>Join #{incidentId.toLowerCase()}</span>
        </div>
      </Card>
    </a>
  );
}

const styles = stylex.create({
  link: {display: 'block'},
  card: {
    backgroundColor: {
      default: background.primary,
      ':hover': background.transparentNeutralMuted,
    },
    cursor: 'pointer',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '200ms',
  },
  content: {display: 'flex', alignItems: 'center', gap: '12px'},
  icon: {height: '28px', width: '28px'},
  label: {color: content.headings, fontSize: '16px', lineHeight: '24px', fontWeight: 600},
});
