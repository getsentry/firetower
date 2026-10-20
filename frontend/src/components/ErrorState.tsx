import type {ReactNode} from 'react';
import * as stylex from '@stylexjs/stylex';
import {Link} from '@tanstack/react-router';

import {background, content, fontWeight, space} from '../styles/tokens.stylex';

interface ErrorStateProps {
  title?: string;
  description?: ReactNode;
  showBackButton?: boolean;
}

export const ErrorState = ({
  title = 'Something went wrong',
  description,
  showBackButton = false,
}: ErrorStateProps) => {
  return (
    <div {...stylex.props(styles.container)}>
      <div {...stylex.props(styles.content)}>
        <h2 {...stylex.props(styles.title)}>{title}</h2>
        {description && <div {...stylex.props(styles.description)}>{description}</div>}
        {showBackButton && (
          <div {...stylex.props(styles.backContainer)}>
            <Link to="/" {...stylex.props(styles.backLink)}>
              <span>{String.fromCharCode(8592)}</span>
              <span>All Incidents</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

const styles = stylex.create({
  container: {
    display: 'flex',
    minHeight: '40vh',
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {textAlign: 'center'},
  title: {
    color: content.headings,
    marginBottom: space.lg,
    fontSize: 24,
    lineHeight: '32px',
    fontWeight: fontWeight.medium,
  },
  description: {
    color: content.secondary,
    marginBottom: space.lg,
    display: 'flex',
    flexDirection: 'column',
    gap: space.lg,
    marginInline: 'auto',
    maxWidth: 448,
  },
  backContainer: {marginTop: space.xl},
  backLink: {
    color: {default: content.secondary, ':hover': content.accent},
    backgroundColor: {default: null, ':hover': background.secondary},
    paddingInline: space.md,
    paddingBlock: space.sm,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    borderRadius: 2,
    transitionProperty:
      'color, background-color, border-color, text-decoration-color, fill, stroke',
    transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
    transitionDuration: '150ms',
  },
});
