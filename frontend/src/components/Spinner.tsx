import React from 'react';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {border, radius} from '../styles/tokens.stylex';

const spin = stylex.keyframes({to: {transform: 'rotate(360deg)'}});
const styles = stylex.create({
  root: {
    animationName: spin,
    animationDuration: '1s',
    animationTimingFunction: 'linear',
    animationIterationCount: 'infinite',
    borderRadius: radius.full,
    borderStyle: 'solid',
    borderColor: border.secondary,
    borderTopColor: 'transparent',
  },
  sm: {height: 16, width: 16, borderWidth: 2},
  md: {height: 32, width: 32, borderWidth: 2},
  lg: {height: 48, width: 48, borderWidth: 4},
  accessible: {
    position: 'absolute',
    width: 1,
    height: 1,
    padding: 0,
    margin: -1,
    overflow: 'hidden',
    clipPath: 'inset(50%)',
    whiteSpace: 'nowrap',
    borderWidth: 0,
  },
});
const sizes = {sm: styles.sm, md: styles.md, lg: styles.lg};
interface SpinnerProps extends StyledProps<React.HTMLAttributes<HTMLDivElement>> {
  size?: keyof typeof sizes;
  ref?: React.Ref<HTMLDivElement>;
}
export const Spinner = ({size = 'md', style, ref, ...props}: SpinnerProps) => (
  <div
    ref={ref}
    {...stylex.props(styles.root, sizes[size], style)}
    role="status"
    aria-label="Loading"
    data-testid="spinner"
    {...props}
  >
    <span {...stylex.props(styles.accessible)}>Loading...</span>
  </div>
);
