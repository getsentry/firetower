import * as LabelPrimitive from '@radix-ui/react-label';
import {cn} from 'utils/cn';

function Label({className, ...props}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn(
        'text-size-sm font-medium leading-none select-none',
        'peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
        className
      )}
      {...props}
    />
  );
}

export {Label};
