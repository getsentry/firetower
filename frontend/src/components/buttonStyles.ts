import * as stylex from '@stylexjs/stylex';

import {
  background,
  border,
  content,
  fontWeight,
  radius,
  space,
} from '../styles/tokens.stylex';

const styles = stylex.create({
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    transitionProperty: 'all',
    transitionDuration: '150ms',
    cursor: {default: 'pointer', ':disabled': 'not-allowed'},
    userSelect: 'none',
    opacity: {default: 1, ':disabled': 0.5},
  },
  primary: {
    gap: space.xs,
    paddingInline: space.md,
    paddingBlock: space.sm,
    borderRadius: radius.md,
    fontWeight: fontWeight.medium,
    fontSize: 14,
    lineHeight: '20px',
    backgroundColor: background.accentVibrant,
    color: content.onVibrantLight,
    opacity: {default: 1, ':hover': 0.9, ':disabled': {default: 0.5, ':hover': 0.5}},
  },
  secondary: {
    gap: space.xs,
    paddingInline: space.md,
    paddingBlock: space.sm,
    borderRadius: radius.md,
    fontWeight: fontWeight.medium,
    fontSize: 14,
    lineHeight: '20px',
    backgroundColor: {
      default: 'white',
      '@media (prefers-color-scheme: dark)': {
        default: '#404040',
        ':hover': background.transparentNeutralMuted,
      },
      ':hover': background.transparentNeutralMuted,
    },
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: border.secondary,
    color: content.primary,
  },
  icon: {
    padding: space.xs,
    borderRadius: radius.sm,
    color: {default: content.secondary, ':hover': content.primary},
    backgroundColor: {
      default: 'transparent',
      ':hover': background.transparentNeutralMuted,
    },
  },
  close: {
    padding: 2,
    borderRadius: radius.sm,
    color: {default: content.disabled, ':hover': content.primary},
    backgroundColor: {
      default: 'transparent',
      ':hover': background.transparentNeutralMuted,
    },
  },
  default: {paddingInline: space.md, paddingBlock: space.sm, height: 32},
  sm: {paddingInline: space.sm, height: 28, fontSize: 12, lineHeight: '16px'},
  lg: {paddingInline: space.lg, height: 40},
  iconSize: {height: 32, width: 32, padding: 0},
});

const variants = {
  primary: styles.primary,
  secondary: styles.secondary,
  icon: styles.icon,
  close: styles.close,
};
const sizes = {
  default: styles.default,
  sm: styles.sm,
  lg: styles.lg,
  icon: styles.iconSize,
};
type ButtonOptions = {
  variant?: keyof typeof variants | null;
  size?: keyof typeof sizes | null;
};
function buttonStyles({
  variant = 'primary',
  size = 'default',
}: ButtonOptions = {}): stylex.StyleXStyles {
  return [styles.base, variant && variants[variant], size && sizes[size]];
}

export {buttonStyles, type ButtonOptions};
