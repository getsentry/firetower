import React from 'react';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, content, fontSize, radius, space} from '../styles/tokens.stylex';

const styles = stylex.create({
  root: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: space.xs,
    paddingInline: space.md,
    paddingBlock: space.xs,
    backgroundColor: {
      default: background.tertiary,
      '@media (prefers-color-scheme: dark)': background.secondary,
    },
    borderRadius: radius.xs,
    fontSize: fontSize.sm,
    color: content.secondary,
  },
});
interface TagProps extends StyledProps<React.HTMLAttributes<HTMLSpanElement>> {
  children: React.ReactNode;
  action?: React.ReactNode;
  ref?: React.Ref<HTMLSpanElement>;
}
export function Tag({children, style, action, ref, ...props}: TagProps) {
  return (
    <span ref={ref} {...stylex.props(styles.root, style)} {...props}>
      <span>{children}</span>
      {action}
    </span>
  );
}
