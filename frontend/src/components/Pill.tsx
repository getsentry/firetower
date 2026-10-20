import React from 'react';
import * as stylex from '@stylexjs/stylex';
import {cn} from 'utils/cn';

import {
  background,
  content,
  fontSize,
  fontWeight,
  radius,
  space,
} from '../styles/tokens.stylex';

const styles = stylex.create({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    paddingInline: space.lg,
    paddingBlock: space.xs,
    borderRadius: radius.full,
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    textTransform: 'uppercase',
    userSelect: 'none',
  },
  singleLine: {
    lineHeight: 1,
  },
  danger: {
    backgroundColor: background.transparentDangerMuted,
    color: content.danger,
  },
  warning: {
    backgroundColor: background.transparentWarningMuted,
    color: content.warning,
  },
  accent: {
    backgroundColor: background.transparentAccentMuted,
    color: content.accent,
  },
  success: {
    backgroundColor: background.transparentSuccessMuted,
    color: content.success,
  },
  neutral: {
    backgroundColor: background.transparentNeutralMuted,
    color: content.secondary,
  },
  critical: {
    backgroundColor: background.dangerVibrant,
    color: content.onVibrantLight,
  },
  default: {
    backgroundColor: background.secondary,
    color: content.secondary,
  },
});

const variants = {
  Active: styles.danger,
  Mitigated: styles.warning,
  Postmortem: styles.accent,
  Done: styles.success,
  Canceled: styles.neutral,
  Todo: styles.neutral,
  'In Progress': styles.warning,
  P0: styles.critical,
  P1: styles.danger,
  P2: styles.warning,
  P3: styles.accent,
  P4: styles.neutral,
  T0: styles.critical,
  T1: styles.danger,
  T2: styles.warning,
  T3: styles.accent,
  T4: styles.neutral,
  private: styles.danger,
  default: styles.default,
};

interface PillProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof variants | null;
  ref?: React.Ref<HTMLDivElement>;
}

const Pill = ({children, className, variant = 'default', ref, ...props}: PillProps) => {
  const singleLine = cn('leading-none', className).split(' ').includes('leading-none');
  const {className: stylexClassName} = stylex.props(
    styles.base,
    singleLine && styles.singleLine,
    variant === null ? null : variants[variant]
  );

  return (
    <div ref={ref} className={cn(stylexClassName, className)} {...props}>
      {children}
    </div>
  );
};

export {Pill, type PillProps};
