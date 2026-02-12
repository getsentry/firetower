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

function TooltipContent({
  className,
  sideOffset = 4,
  ref,
  children,
  ...props
}: TooltipContentProps) {
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
      >
        {children}
        <TooltipPrimitive.Arrow asChild>
          <svg
            className="-my-px fill-background-primary stroke-gray-200"
            width={10}
            height={5}
            viewBox="0 0 30 10"
            preserveAspectRatio="none"
          >
            <polygon points="0,0 30,0 15,10" className="stroke-none" />
            <polyline points="0,0 15,10 30,0" fill="none" strokeWidth={3} />
          </svg>
        </TooltipPrimitive.Arrow>
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  );
}

export {TooltipProvider, Tooltip, TooltipTrigger, TooltipContent};
