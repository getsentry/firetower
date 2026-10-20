import * as stylex from '@stylexjs/stylex';
import {Tooltip, TooltipContent, TooltipTrigger} from 'components/Tooltip';
import {Info} from 'lucide-react';

import {
  background,
  content,
  fontFamily,
  fontSize,
  fontWeight,
  graphics,
  space,
} from '../../../styles/tokens.stylex';

export function AvailabilityTooltip() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          {...stylex.props(styles.trigger)}
          aria-label="How availability is calculated"
        >
          <Info size={18} />
        </button>
      </TooltipTrigger>
      <TooltipContent align="start" style={styles.tooltip}>
        <h3 {...stylex.props(styles.heading)}>How availability is calculated</h3>
        <p {...stylex.props(styles.paragraph)}>
          Availability percentage is calculated as:
        </p>
        <p {...stylex.props(styles.formula)}>
          (Total Time &minus; Downtime) / Total Time &times; 100
        </p>
        <p {...stylex.props(styles.paragraph)}>
          Only <strong>T0 service tier</strong> incidents with{' '}
          <strong>availability impact</strong> are included.
        </p>
        <p {...stylex.props(styles.details)}>
          Downtime is captured in the time period the incident was created.
        </p>
        <h4 {...stylex.props(styles.subheading)}>Color thresholds</h4>
        <ul {...stylex.props(styles.thresholds)}>
          <li {...stylex.props(styles.threshold)}>
            <span {...stylex.props(styles.success)} />
            <span>Green: &ge; 99.9%</span>
          </li>
          <li {...stylex.props(styles.threshold)}>
            <span {...stylex.props(styles.warning)} />
            <span>Yellow: &ge; 99.85%</span>
          </li>
          <li {...stylex.props(styles.threshold)}>
            <span {...stylex.props(styles.danger)} />
            <span>Red: &lt; 99.85%</span>
          </li>
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}

const styles = stylex.create({
  trigger: {
    color: {default: content.secondary, ':hover': content.primary},
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
  tooltip: {fontSize: fontSize.sm, maxWidth: 384},
  heading: {color: content.headings, marginBottom: space.sm, fontWeight: 600},
  paragraph: {color: content.secondary, marginBottom: space.sm},
  formula: {
    color: content.primary,
    backgroundColor: background.secondary,
    marginBottom: space.sm,
    paddingInline: space.sm,
    paddingBlock: space.xs,
    fontSize: fontSize.xs,
    borderRadius: 4,
    fontFamily: fontFamily.mono,
  },
  details: {color: content.secondary, marginBottom: space.md},
  subheading: {
    color: content.headings,
    marginBottom: space.xs,
    fontWeight: fontWeight.medium,
  },
  thresholds: {
    color: content.secondary,
    display: 'flex',
    flexDirection: 'column',
    gap: space.xs,
  },
  threshold: {gap: space.xs, display: 'flex', alignItems: 'center'},
  success: {
    backgroundColor: graphics.successModerate,
    display: 'inline-block',
    width: 12,
    height: 12,
    borderRadius: 4,
  },
  warning: {
    backgroundColor: graphics.warningModerate,
    display: 'inline-block',
    width: 12,
    height: 12,
    borderRadius: 4,
  },
  danger: {
    backgroundColor: graphics.dangerModerate,
    display: 'inline-block',
    width: 12,
    height: 12,
    borderRadius: 4,
  },
});
