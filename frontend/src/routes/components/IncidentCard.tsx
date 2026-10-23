import * as stylex from '@stylexjs/stylex';
import {Link} from '@tanstack/react-router';
import {Pill} from 'components/Pill';

import {
  background,
  content,
  fontSize,
  fontWeight,
  lineHeight,
  radius,
  space,
} from '../../styles/tokens.stylex';
import type {IncidentListItem} from '../queries/incidentsQueryOptions';

interface IncidentCardProps {
  incident: IncidentListItem;
}

export const IncidentCard = ({incident}: IncidentCardProps) => {
  const createdAt = new Date(incident.created_at);

  return (
    <Link
      to="/$incidentId"
      params={{incidentId: incident.id}}
      {...stylex.props(styles.link)}
      preload={'intent'}
    >
      <div {...stylex.props(styles.card)} data-testid={`incident-card-${incident.id}`}>
        <div {...stylex.props(styles.layout)}>
          <div {...stylex.props(styles.summary)}>
            <h3 {...stylex.props(styles.title)}>{incident.title}</h3>
            <span {...stylex.props(styles.identifier)}>
              {incident.is_private && <span aria-label="Private incident">🔒</span>}
              {incident.id}
            </span>
            <div {...stylex.props(styles.pills)}>
              <Pill variant={incident.severity}>{incident.severity}</Pill>
              <Pill variant={incident.status}>{incident.status}</Pill>
              {incident.is_private && <Pill variant="private">Private</Pill>}
            </div>
            {incident.description ? (
              <p {...stylex.props(styles.description)}>{incident.description}</p>
            ) : null}
          </div>
          <div {...stylex.props(styles.metadata)}>
            <time dateTime={incident.created_at}>
              {createdAt.toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </time>
            <p>
              Opened{' '}
              {createdAt.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
                timeZoneName: 'short',
              })}
            </p>
            {incident.captain && (
              <p {...stylex.props(styles.captain)}>Captain: {incident.captain}</p>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
};

const styles = stylex.create({
  link: {display: 'block', textDecoration: 'none'},
  card: {
    backgroundColor: {
      default: background.primary,
      ':hover': background.transparentNeutralMuted,
    },
    borderRadius: radius.lg,
    padding: space.xl,
    cursor: 'pointer',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '200ms',
  },
  layout: {gap: space.xl, display: 'flex', justifyContent: 'space-between'},
  summary: {minWidth: 0, flex: '1 1 0%'},
  title: {
    fontSize: fontSize.xl,
    color: content.headings,
    fontWeight: 600,
    userSelect: 'text',
  },
  identifier: {
    fontSize: fontSize.lg,
    color: content.secondary,
    marginTop: space.sm,
    gap: space.xs,
    fontWeight: fontWeight.regular,
    display: 'flex',
    alignItems: 'center',
    lineHeight: 1,
    userSelect: 'text',
  },
  pills: {gap: space.md, marginTop: space.md, display: 'flex'},
  description: {
    color: content.secondary,
    fontSize: fontSize.sm,
    lineHeight: lineHeight.comfortable,
    marginTop: space.md,
    display: '-webkit-box',
    WebkitBoxOrient: 'vertical',
    WebkitLineClamp: 1,
    overflow: 'hidden',
    userSelect: 'none',
  },
  metadata: {
    fontSize: fontSize.sm,
    color: content.secondary,
    flexShrink: 0,
    textAlign: 'right',
    userSelect: 'none',
  },
  captain: {marginTop: space.xs},
});
