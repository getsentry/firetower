import * as stylex from '@stylexjs/stylex';

export const background = stylex.defineVars({
  primary: 'var(--scraps-background-primary)',
  secondary: 'var(--scraps-background-secondary)',
  tertiary: 'var(--scraps-background-tertiary)',
  overlay: 'var(--scraps-background-overlay)',
  accentVibrant: 'var(--scraps-background-accent-vibrant)',
  promotionVibrant: 'var(--scraps-background-promotion-vibrant)',
  dangerVibrant: 'var(--scraps-background-danger-vibrant)',
  warningVibrant: 'var(--scraps-background-warning-vibrant)',
  successVibrant: 'var(--scraps-background-success-vibrant)',
  transparentNeutralMuted: 'var(--scraps-background-transparent-neutral-muted)',
  transparentAccentMuted: 'var(--scraps-background-transparent-accent-muted)',
  transparentPromotionMuted: 'var(--scraps-background-transparent-promotion-muted)',
  transparentDangerMuted: 'var(--scraps-background-transparent-danger-muted)',
  transparentWarningMuted: 'var(--scraps-background-transparent-warning-muted)',
  transparentSuccessMuted: 'var(--scraps-background-transparent-success-muted)',
});

export const border = stylex.defineVars({
  primary: 'var(--scraps-border-primary)',
  secondary: 'var(--scraps-border-secondary)',
  neutralMuted: 'var(--scraps-border-neutral-muted)',
  neutralModerate: 'var(--scraps-border-neutral-moderate)',
  neutralVibrant: 'var(--scraps-border-neutral-vibrant)',
  accentMuted: 'var(--scraps-border-accent-muted)',
  accentModerate: 'var(--scraps-border-accent-moderate)',
  accentVibrant: 'var(--scraps-border-accent-vibrant)',
  promotionMuted: 'var(--scraps-border-promotion-muted)',
  promotionModerate: 'var(--scraps-border-promotion-moderate)',
  promotionVibrant: 'var(--scraps-border-promotion-vibrant)',
  dangerMuted: 'var(--scraps-border-danger-muted)',
  dangerModerate: 'var(--scraps-border-danger-moderate)',
  dangerVibrant: 'var(--scraps-border-danger-vibrant)',
  warningMuted: 'var(--scraps-border-warning-muted)',
  warningModerate: 'var(--scraps-border-warning-moderate)',
  warningVibrant: 'var(--scraps-border-warning-vibrant)',
  successMuted: 'var(--scraps-border-success-muted)',
  successModerate: 'var(--scraps-border-success-moderate)',
  successVibrant: 'var(--scraps-border-success-vibrant)',
  onVibrantLight: 'var(--scraps-border-on-vibrant-light)',
  onVibrantDark: 'var(--scraps-border-on-vibrant-dark)',
  transparentNeutralMuted: 'var(--scraps-border-transparent-neutral-muted)',
  transparentNeutralModerate: 'var(--scraps-border-transparent-neutral-moderate)',
  transparentNeutralVibrant: 'var(--scraps-border-transparent-neutral-vibrant)',
  transparentAccentMuted: 'var(--scraps-border-transparent-accent-muted)',
  transparentAccentModerate: 'var(--scraps-border-transparent-accent-moderate)',
  transparentAccentVibrant: 'var(--scraps-border-transparent-accent-vibrant)',
  transparentPromotionMuted: 'var(--scraps-border-transparent-promotion-muted)',
  transparentPromotionModerate: 'var(--scraps-border-transparent-promotion-moderate)',
  transparentPromotionVibrant: 'var(--scraps-border-transparent-promotion-vibrant)',
  transparentDangerMuted: 'var(--scraps-border-transparent-danger-muted)',
  transparentDangerModerate: 'var(--scraps-border-transparent-danger-moderate)',
  transparentDangerVibrant: 'var(--scraps-border-transparent-danger-vibrant)',
  transparentWarningMuted: 'var(--scraps-border-transparent-warning-muted)',
  transparentWarningModerate: 'var(--scraps-border-transparent-warning-moderate)',
  transparentWarningVibrant: 'var(--scraps-border-transparent-warning-vibrant)',
  transparentSuccessMuted: 'var(--scraps-border-transparent-success-muted)',
  transparentSuccessModerate: 'var(--scraps-border-transparent-success-moderate)',
  transparentSuccessVibrant: 'var(--scraps-border-transparent-success-vibrant)',
});

export const content = stylex.defineVars({
  primary: 'var(--scraps-content-primary)',
  secondary: 'var(--scraps-content-secondary)',
  accent: 'var(--scraps-content-accent)',
  promotion: 'var(--scraps-content-promotion)',
  danger: 'var(--scraps-content-danger)',
  warning: 'var(--scraps-content-warning)',
  success: 'var(--scraps-content-success)',
  disabled: 'var(--scraps-content-disabled)',
  headings: 'var(--scraps-content-headings)',
  onVibrantLight: 'var(--scraps-content-on-vibrant-light)',
  onVibrantDark: 'var(--scraps-content-on-vibrant-dark)',
});

export const graphics = stylex.defineVars({
  neutralMuted: 'var(--scraps-graphics-neutral-muted)',
  neutralModerate: 'var(--scraps-graphics-neutral-moderate)',
  neutralVibrant: 'var(--scraps-graphics-neutral-vibrant)',
  accentMuted: 'var(--scraps-graphics-accent-muted)',
  accentModerate: 'var(--scraps-graphics-accent-moderate)',
  accentVibrant: 'var(--scraps-graphics-accent-vibrant)',
  promotionMuted: 'var(--scraps-graphics-promotion-muted)',
  promotionModerate: 'var(--scraps-graphics-promotion-moderate)',
  promotionVibrant: 'var(--scraps-graphics-promotion-vibrant)',
  dangerMuted: 'var(--scraps-graphics-danger-muted)',
  dangerModerate: 'var(--scraps-graphics-danger-moderate)',
  dangerVibrant: 'var(--scraps-graphics-danger-vibrant)',
  warningMuted: 'var(--scraps-graphics-warning-muted)',
  warningModerate: 'var(--scraps-graphics-warning-moderate)',
  warningVibrant: 'var(--scraps-graphics-warning-vibrant)',
  successMuted: 'var(--scraps-graphics-success-muted)',
  successModerate: 'var(--scraps-graphics-success-moderate)',
  successVibrant: 'var(--scraps-graphics-success-vibrant)',
});

export const space = stylex.defineVars({
  '0': 'var(--scraps-space-0)',
  '2xs': 'var(--scraps-space-2xs)',
  xs: 'var(--scraps-space-xs)',
  sm: 'var(--scraps-space-sm)',
  md: 'var(--scraps-space-md)',
  lg: 'var(--scraps-space-lg)',
  xl: 'var(--scraps-space-xl)',
  '2xl': 'var(--scraps-space-2xl)',
  '3xl': 'var(--scraps-space-3xl)',
});

export const radius = stylex.defineVars({
  '0': 'var(--scraps-radius-0)',
  '2xs': 'var(--scraps-radius-2xs)',
  xs: 'var(--scraps-radius-xs)',
  sm: 'var(--scraps-radius-sm)',
  md: 'var(--scraps-radius-md)',
  lg: 'var(--scraps-radius-lg)',
  xl: 'var(--scraps-radius-xl)',
  '2xl': 'var(--scraps-radius-2xl)',
  full: 'var(--scraps-radius-full)',
});

export const fontSize = stylex.defineVars({
  xs: 'var(--scraps-font-size-xs)',
  sm: 'var(--scraps-font-size-sm)',
  md: 'var(--scraps-font-size-md)',
  lg: 'var(--scraps-font-size-lg)',
  xl: 'var(--scraps-font-size-xl)',
  '2xl': 'var(--scraps-font-size-2xl)',
  '3xl': 'var(--scraps-font-size-3xl)',
  '4xl': 'var(--scraps-font-size-4xl)',
});

export const fontWeight = stylex.defineVars({
  regular: 'var(--scraps-font-weight-regular)',
  medium: 'var(--scraps-font-weight-medium)',
});

export const fontFamily = stylex.defineVars({
  sans: 'var(--scraps-font-family-sans)',
  mono: 'var(--scraps-font-family-mono)',
});

export const lineHeight = stylex.defineVars({
  compressed: 'var(--scraps-line-height-compressed)',
  default: 'var(--scraps-line-height-default)',
  comfortable: 'var(--scraps-line-height-comfortable)',
  fixed: 'var(--scraps-line-height-fixed)',
});
