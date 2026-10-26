import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, content, radius} from '../styles/tokens.stylex';

const styles = stylex.create({
  root: {
    backgroundColor: background.tertiary,
    color: content.secondary,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.full,
    fontWeight: 600,
    flexShrink: 0,
  },
  sm: {height: 28, width: 28, fontSize: 14, lineHeight: '20px'},
  md: {height: 40, width: 40, fontSize: 16, lineHeight: '24px'},
  initials: {lineHeight: 1},
});
const sizes = {sm: styles.sm, md: styles.md};
export type AvatarProps = StyledProps<{
  name: string;
  src?: string | null;
  alt?: string;
  size?: keyof typeof sizes;
}>;
function getInitials(name: string): string {
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}
export function Avatar({name, src, alt, style, size = 'md'}: AvatarProps) {
  if (!name) return null;
  if (src)
    return (
      <img
        src={src}
        alt={alt || name}
        {...stylex.props(styles.root, sizes[size], style)}
      />
    );
  return (
    <div {...stylex.props(styles.root, sizes[size], styles.initials, style)}>
      {getInitials(name)}
    </div>
  );
}
