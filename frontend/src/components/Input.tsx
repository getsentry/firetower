import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {content, fontSize, radius} from '../styles/tokens.stylex';

const styles = stylex.create({
  root: {
    borderColor: '#e5e7eb',
    borderWidth: 1,
    borderStyle: 'solid',
    height: 32,
    width: '100%',
    borderRadius: radius.md,
    backgroundColor: 'transparent',
    paddingInline: 12,
    paddingBlock: 4,
    fontSize: fontSize.sm,
    color: {'::placeholder': content.disabled},
    pointerEvents: {default: 'auto', ':disabled': 'none'},
    cursor: {default: 'auto', ':disabled': 'not-allowed'},
    opacity: {default: 1, ':disabled': 0.5},
  },
});
function Input({style, type, ...props}: StyledProps<React.ComponentProps<'input'>>) {
  return <input type={type} {...stylex.props(styles.root, style)} {...props} />;
}
export {Input};
