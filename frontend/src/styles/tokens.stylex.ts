import * as stylex from '@stylexjs/stylex';

export const background = stylex.defineVars({
  primary: {default: '#FFFFFF', '@media (prefers-color-scheme: dark)': '#2E2936'},
  secondary: {default: '#F8F8F9', '@media (prefers-color-scheme: dark)': '#24202B'},
  tertiary: {default: '#F0F0F2', '@media (prefers-color-scheme: dark)': '#1B1821'},
  overlay: {default: '#FFFFFF', '@media (prefers-color-scheme: dark)': '#393442'},
  accentVibrant: {default: '#7553FF', '@media (prefers-color-scheme: dark)': '#7553FF'},
  promotionVibrant: {
    default: '#FC5CB4',
    '@media (prefers-color-scheme: dark)': '#FF45A8',
  },
  dangerVibrant: {default: '#FF002B', '@media (prefers-color-scheme: dark)': '#FF002B'},
  warningVibrant: {default: '#FFCE00', '@media (prefers-color-scheme: dark)': '#FFCE00'},
  successVibrant: {default: '#00F261', '@media (prefers-color-scheme: dark)': '#00F261'},
  transparentNeutralMuted: {
    default: '#0000200F',
    '@media (prefers-color-scheme: dark)': '#C0A8F81A',
  },
  transparentAccentMuted: {
    default: '#0008F012',
    '@media (prefers-color-scheme: dark)': '#4828B894',
  },
  transparentPromotionMuted: {
    default: '#F000901A',
    '@media (prefers-color-scheme: dark)': '#F800782E',
  },
  transparentDangerMuted: {
    default: '#F828081C',
    '@media (prefers-color-scheme: dark)': '#F8000033',
  },
  transparentWarningMuted: {
    default: '#E0B01030',
    '@media (prefers-color-scheme: dark)': '#E8380029',
  },
  transparentSuccessMuted: {
    default: '#00B8001C',
    '@media (prefers-color-scheme: dark)': '#00F8001F',
  },
});

export const border = stylex.defineVars({
  primary: {default: '#DAD9DE', '@media (prefers-color-scheme: dark)': '#141119'},
  secondary: {default: '#E6E6E9', '@media (prefers-color-scheme: dark)': '#1B1821'},
  neutralMuted: {default: '#DAD9DE', '@media (prefers-color-scheme: dark)': '#534D5E'},
  neutralModerate: {default: '#C0BEC6', '@media (prefers-color-scheme: dark)': '#898294'},
  neutralVibrant: {default: '#A29FAA', '@media (prefers-color-scheme: dark)': '#B5B0BD'},
  accentMuted: {default: '#D4D3FF', '@media (prefers-color-scheme: dark)': '#4C39A5'},
  accentModerate: {default: '#B7B2FF', '@media (prefers-color-scheme: dark)': '#7553FF'},
  accentVibrant: {default: '#7553FF', '@media (prefers-color-scheme: dark)': '#7553FF'},
  promotionMuted: {default: '#FFC2E3', '@media (prefers-color-scheme: dark)': '#8C1758'},
  promotionModerate: {
    default: '#FF93CE',
    '@media (prefers-color-scheme: dark)': '#C9598E',
  },
  promotionVibrant: {
    default: '#FF70BC',
    '@media (prefers-color-scheme: dark)': '#FF45A8',
  },
  dangerMuted: {default: '#FFC4BD', '@media (prefers-color-scheme: dark)': '#9A0116'},
  dangerModerate: {default: '#FF978F', '@media (prefers-color-scheme: dark)': '#FF002B'},
  dangerVibrant: {default: '#FF002B', '@media (prefers-color-scheme: dark)': '#FF002B'},
  warningMuted: {default: '#F2D88E', '@media (prefers-color-scheme: dark)': '#B47B00'},
  warningModerate: {default: '#EDCA60', '@media (prefers-color-scheme: dark)': '#CA9B00'},
  warningVibrant: {default: '#FFCE00', '@media (prefers-color-scheme: dark)': '#FFCE00'},
  successMuted: {default: '#B5EABB', '@media (prefers-color-scheme: dark)': '#006D00'},
  successModerate: {default: '#7CD88A', '@media (prefers-color-scheme: dark)': '#00A719'},
  successVibrant: {default: '#00F261', '@media (prefers-color-scheme: dark)': '#00F261'},
  onVibrantLight: {default: '#FFFFFF', '@media (prefers-color-scheme: dark)': '#FFFFFF'},
  onVibrantDark: {default: '#000000', '@media (prefers-color-scheme: dark)': '#000000'},
  transparentNeutralMuted: {
    default: '#00002026',
    '@media (prefers-color-scheme: dark)': '#C0A8E03D',
  },
  transparentNeutralModerate: {
    default: '#10082845',
    '@media (prefers-color-scheme: dark)': '#D0C0E0AD',
  },
  transparentNeutralVibrant: {
    default: '#10082863',
    '@media (prefers-color-scheme: dark)': '#D0C0E0AD',
  },
  transparentAccentMuted: {
    default: '#1008F82E',
    '@media (prefers-color-scheme: dark)': '#6048D0C9',
  },
  transparentAccentModerate: {
    default: '#1808F84F',
    '@media (prefers-color-scheme: dark)': '#7553FF',
  },
  transparentAccentVibrant: {
    default: '#4010F8B8',
    '@media (prefers-color-scheme: dark)': '#7553FF',
  },
  transparentPromotionMuted: {
    default: '#F840A852',
    '@media (prefers-color-scheme: dark)': '#B80870AB',
  },
  transparentPromotionModerate: {
    default: '#F8089070',
    '@media (prefers-color-scheme: dark)': '#D86098ED',
  },
  transparentPromotionVibrant: {
    default: '#F800888F',
    '@media (prefers-color-scheme: dark)': '#FF45A8',
  },
  transparentDangerMuted: {
    default: '#F8483052',
    '@media (prefers-color-scheme: dark)': '#F000007A',
  },
  transparentDangerModerate: {
    default: '#F8201078',
    '@media (prefers-color-scheme: dark)': '#FF002B',
  },
  transparentDangerVibrant: {
    default: '#FF002B',
    '@media (prefers-color-scheme: dark)': '#FF002B',
  },
  transparentWarningMuted: {
    default: '#E8B8308C',
    '@media (prefers-color-scheme: dark)': '#F8A800BA',
  },
  transparentWarningModerate: {
    default: '#E8B828BD',
    '@media (prefers-color-scheme: dark)': '#F0B800D6',
  },
  transparentWarningVibrant: {
    default: '#FFCE00',
    '@media (prefers-color-scheme: dark)': '#FFCE00',
  },
  transparentSuccessMuted: {
    default: '#00B8104A',
    '@media (prefers-color-scheme: dark)': '#00F8004F',
  },
  transparentSuccessModerate: {
    default: '#10B8288C',
    '@media (prefers-color-scheme: dark)': '#00D820C4',
  },
  transparentSuccessVibrant: {
    default: '#00F261',
    '@media (prefers-color-scheme: dark)': '#00F261',
  },
});

export const content = stylex.defineVars({
  primary: {default: '#302E36', '@media (prefers-color-scheme: dark)': '#E7E5EA'},
  secondary: {default: '#6A6772', '@media (prefers-color-scheme: dark)': '#B5B0BD'},
  accent: {default: '#653DE9', '@media (prefers-color-scheme: dark)': '#ABA8F8'},
  promotion: {default: '#C8007E', '@media (prefers-color-scheme: dark)': '#EA95B9'},
  danger: {default: '#D50000', '@media (prefers-color-scheme: dark)': '#F6938C'},
  warning: {default: '#A45200', '@media (prefers-color-scheme: dark)': '#FFCE00'},
  success: {default: '#008900', '@media (prefers-color-scheme: dark)': '#5ECE73'},
  disabled: {default: '#878490', '@media (prefers-color-scheme: dark)': '#958E9F'},
  headings: {default: '#181225', '@media (prefers-color-scheme: dark)': '#FFFFFF'},
  onVibrantLight: {default: '#FFFFFF', '@media (prefers-color-scheme: dark)': '#FFFFFF'},
  onVibrantDark: {default: '#000000', '@media (prefers-color-scheme: dark)': '#000000'},
});

export const graphics = stylex.defineVars({
  neutralMuted: {default: '#DAD9DE', '@media (prefers-color-scheme: dark)': '#534D5E'},
  neutralModerate: {default: '#C0BEC6', '@media (prefers-color-scheme: dark)': '#898294'},
  neutralVibrant: {default: '#787581', '@media (prefers-color-scheme: dark)': '#A49EAE'},
  accentMuted: {default: '#D4D3FF', '@media (prefers-color-scheme: dark)': '#4C39A5'},
  accentModerate: {default: '#B7B2FF', '@media (prefers-color-scheme: dark)': '#7553FF'},
  accentVibrant: {default: '#7553FF', '@media (prefers-color-scheme: dark)': '#9A94F1'},
  promotionMuted: {default: '#FFC2E3', '@media (prefers-color-scheme: dark)': '#8C1758'},
  promotionModerate: {
    default: '#FF93CE',
    '@media (prefers-color-scheme: dark)': '#C9598E',
  },
  promotionVibrant: {
    default: '#D9008D',
    '@media (prefers-color-scheme: dark)': '#DF7DA9',
  },
  dangerMuted: {default: '#FFC4BD', '@media (prefers-color-scheme: dark)': '#9A0116'},
  dangerModerate: {default: '#FF978F', '@media (prefers-color-scheme: dark)': '#FF002B'},
  dangerVibrant: {default: '#FF002B', '@media (prefers-color-scheme: dark)': '#ED7B74'},
  warningMuted: {default: '#F2D88E', '@media (prefers-color-scheme: dark)': '#B47B00'},
  warningModerate: {default: '#EDCA60', '@media (prefers-color-scheme: dark)': '#CA9B00'},
  warningVibrant: {default: '#D59600', '@media (prefers-color-scheme: dark)': '#FFCE00'},
  successMuted: {default: '#B5EABB', '@media (prefers-color-scheme: dark)': '#006D00'},
  successModerate: {default: '#7CD88A', '@media (prefers-color-scheme: dark)': '#00A719'},
  successVibrant: {default: '#009800', '@media (prefers-color-scheme: dark)': '#5ECE73'},
});

export const space = stylex.defineVars({
  '0': '0px',
  '2xs': '2px',
  xs: '4px',
  sm: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  '2xl': '24px',
  '3xl': '32px',
});

export const radius = stylex.defineVars({
  '0': '0px',
  '2xs': '3px',
  xs: '4px',
  sm: '5px',
  md: '6px',
  lg: '8px',
  xl: '12px',
  '2xl': '16px',
  full: '999px',
});

export const fontSize = stylex.defineVars({
  xs: '11px',
  sm: '12px',
  md: '14px',
  lg: '16px',
  xl: '20px',
  '2xl': '24px',
  '3xl': '32px',
  '4xl': '40px',
});

export const fontWeight = stylex.defineVars({
  regular: '400',
  medium: '500',
});

export const fontFamily = stylex.defineVars({
  sans: "Rubik, 'Avenir Next', sans-serif",
  mono: "'Roboto Mono', Monaco, Consolas, 'Courier New', monospace",
});

export const lineHeight = stylex.defineVars({
  compressed: '1',
  default: '1.2',
  comfortable: '1.4',
  fixed: '1rem',
});
