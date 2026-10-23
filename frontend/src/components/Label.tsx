import * as LabelPrimitive from '@radix-ui/react-label';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {fontSize, fontWeight} from '../styles/tokens.stylex';

const styles = stylex.create({
  root: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.medium,
    lineHeight: 1,
    userSelect: 'none',
  },
});
function Label({
  style,
  ...props
}: StyledProps<React.ComponentProps<typeof LabelPrimitive.Root>>) {
  return <LabelPrimitive.Root {...stylex.props(styles.root, style)} {...props} />;
}
export {Label};
