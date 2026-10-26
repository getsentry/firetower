import type {StyleXStyles} from '@stylexjs/stylex';

export type StyledProps<Props> = Props extends unknown
  ? Omit<Props, 'className' | 'style'> & {
      className?: never;
      style?: StyleXStyles;
    }
  : never;
