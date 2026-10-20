import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, radius} from '../styles/tokens.stylex';

const pulse = stylex.keyframes({'50%': {opacity: 0.5}});
const styles = stylex.create({
  root: {
    animationName: pulse,
    animationDuration: '2s',
    animationTimingFunction: 'cubic-bezier(0.4, 0, 0.6, 1)',
    animationIterationCount: 'infinite',
    borderRadius: radius.sm,
    backgroundColor: background.secondary,
  },
});
export const Skeleton = ({style, ...props}: StyledProps<React.ComponentProps<'div'>>) => (
  <div {...stylex.props(styles.root, style)} aria-hidden="true" {...props} />
);
