import {cn} from 'utils/cn';

function Input({className, type, ...props}: React.ComponentProps<'input'>) {
  return (
    <input
      type={type}
      className={cn(
        'border-gray-200 h-8 w-full rounded-radius-md border bg-transparent px-3 py-1 text-size-sm',
        'placeholder:text-content-disabled',
        'focus:outline-auto',
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
        className
      )}
      {...props}
    />
  );
}

export {Input};
