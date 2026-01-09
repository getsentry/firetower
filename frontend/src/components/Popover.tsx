import * as PopoverPrimitive from '@radix-ui/react-popover';
import {cn} from 'utils/cn';

const Popover = PopoverPrimitive.Root;

const PopoverTrigger = PopoverPrimitive.Trigger;

const PopoverAnchor = PopoverPrimitive.Anchor;

interface PopoverContentProps extends React.ComponentPropsWithoutRef<
  typeof PopoverPrimitive.Content
> {
  ref?: React.Ref<HTMLDivElement>;
}

function PopoverContent({
  className,
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
        className={cn(
          'z-50',
          'rounded-radius-md',
          'border',
          'border-gray-200',
          'bg-background-primary',
          'p-space-md',
          'shadow-lg',
          'outline-none',
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}

export {Popover, PopoverTrigger, PopoverContent, PopoverAnchor};
