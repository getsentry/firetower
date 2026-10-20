import React from 'react';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, content, radius, space} from '../styles/tokens.stylex';

const styles = stylex.create({
  root: {
    backgroundColor: background.primary,
    borderRadius: radius.lg,
    padding: space['2xl'],
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  title: {
    fontSize: 18,
    lineHeight: '28px',
    fontWeight: 600,
    marginBottom: space.xl,
    color: content.headings,
  },
  sm: {fontSize: 14, lineHeight: '20px'},
  base: {fontSize: 16, lineHeight: '24px'},
  lg: {fontSize: 18, lineHeight: '28px'},
  xl: {fontSize: 20, lineHeight: '28px'},
  '2xl': {fontSize: 24, lineHeight: '32px'},
});
const sizes = {
  sm: styles.sm,
  base: styles.base,
  lg: styles.lg,
  xl: styles.xl,
  '2xl': styles['2xl'],
};
type CardProps = StyledProps<React.HTMLAttributes<HTMLDivElement>> & {
  ref?: React.Ref<HTMLDivElement>;
};
type TitleProps = StyledProps<React.HTMLAttributes<HTMLHeadingElement>> & {
  size?: keyof typeof sizes | null;
  ref?: React.Ref<HTMLHeadingElement>;
};
const CardRoot = ({style, ref, ...props}: CardProps) => (
  <div ref={ref} {...stylex.props(styles.root, style)} {...props} />
);
const Title = ({style, size = 'lg', children, ref, ...props}: TitleProps) => (
  <h3 ref={ref} {...stylex.props(styles.title, size && sizes[size], style)} {...props}>
    {children}
  </h3>
);
export const Card = Object.assign(CardRoot, {Title});
