import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';
import {background, radius, space} from '../styles/tokens.stylex';

const TooltipProvider = TooltipPrimitive.Provider;
const Tooltip = TooltipPrimitive.Root;
function TooltipTrigger({
  style,
  ...props
}: StyledProps<React.ComponentProps<typeof TooltipPrimitive.Trigger>>) {
  return <TooltipPrimitive.Trigger {...stylex.props(style)} {...props} />;
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
type TooltipContentProps = StyledProps<
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
> & {ref?: React.Ref<HTMLDivElement>};
function TooltipContent({
  style,
  align = 'center',
  sideOffset = 4,
  ref,
  ...props
}: TooltipContentProps) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        {...stylex.props(styles.content, style)}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}
export {Tooltip, TooltipTrigger, TooltipContent, TooltipProvider};
