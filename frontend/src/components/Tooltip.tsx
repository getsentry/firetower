import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import {cn} from 'utils/cn';

const TooltipProvider = TooltipPrimitive.Provider;

const Tooltip = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

interface TooltipContentProps extends React.ComponentPropsWithoutRef<
  typeof TooltipPrimitive.Content
> {
  ref?: React.Ref<HTMLDivElement>;
}

function TooltipContent({className, sideOffset = 4, ref, ...props}: TooltipContentProps) {
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-50',
          'rounded-radius-md',
          'border',
          'border-gray-200',
          'bg-background-primary',
          'px-space-sm',
          'py-space-xs',
          'text-size-sm',
          'text-content-primary',
          'shadow-lg',
          'animate-in',
          'fade-in-0',
          'zoom-in-95',
          className
        )}
        {...props}
      />
    </TooltipPrimitive.Portal>
  );
}

export {TooltipProvider, Tooltip, TooltipTrigger, TooltipContent};
