import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, radius, space} from '../styles/tokens.stylex';

const Popover = PopoverPrimitive.Root;
function PopoverTrigger({
  style,
  ...props
}: StyledProps<React.ComponentProps<typeof PopoverPrimitive.Trigger>>) {
  return <PopoverPrimitive.Trigger {...stylex.props(style)} {...props} />;
}
function PopoverAnchor({
  style,
  ...props
}: StyledProps<React.ComponentProps<typeof PopoverPrimitive.Anchor>>) {
  return <PopoverPrimitive.Anchor {...stylex.props(style)} {...props} />;
}

const styles = stylex.create({
  content: {
    zIndex: 50,
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'solid',
    borderColor: '#e5e7eb',
    backgroundColor: background.primary,
    padding: space.md,
    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  },
});
type PopoverContentProps = StyledProps<
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
> & {ref?: React.Ref<HTMLDivElement>};
function PopoverContent({
  style,
  align = 'center',
  sideOffset = 4,
  ref,
  ...props
}: PopoverContentProps) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        {...stylex.props(styles.content, style)}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
export {Popover, PopoverTrigger, PopoverContent, PopoverAnchor};
