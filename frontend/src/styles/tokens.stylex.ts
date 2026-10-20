import * as stylex from '@stylexjs/stylex';

export const background = stylex.defineVars({
  secondary: 'var(--scraps-background-secondary)',
  dangerVibrant: 'var(--scraps-background-danger-vibrant)',
  transparentDangerMuted: 'var(--scraps-background-transparent-danger-muted)',
  transparentWarningMuted: 'var(--scraps-background-transparent-warning-muted)',
  transparentAccentMuted: 'var(--scraps-background-transparent-accent-muted)',
  transparentSuccessMuted: 'var(--scraps-background-transparent-success-muted)',
  transparentNeutralMuted: 'var(--scraps-background-transparent-neutral-muted)',
});

export const content = stylex.defineVars({
  secondary: 'var(--scraps-content-secondary)',
  danger: 'var(--scraps-content-danger)',
  warning: 'var(--scraps-content-warning)',
  accent: 'var(--scraps-content-accent)',
  success: 'var(--scraps-content-success)',
  onVibrantLight: 'var(--scraps-content-on-vibrant-light)',
});

export const space = stylex.defineVars({
  xs: 'var(--scraps-space-xs)',
  lg: 'var(--scraps-space-lg)',
});

export const radius = stylex.defineVars({
  full: 'var(--scraps-radius-full)',
});

export const fontSize = stylex.defineVars({
  sm: 'var(--scraps-font-size-sm)',
});

export const fontWeight = stylex.defineVars({
  medium: 'var(--scraps-font-weight-medium)',
});
