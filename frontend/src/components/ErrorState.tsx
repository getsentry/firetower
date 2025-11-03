import type {ReactNode} from 'react';

interface ErrorStateProps {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
}

export const ErrorState = ({
  title = 'Something went wrong :(',
  description,
  action,
}: ErrorStateProps) => {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="text-center">
        <h2 className="text-content-headings mb-space-lg text-2xl font-medium">
          {title}
        </h2>
        {description && (
          <div className="text-content-secondary mx-auto mb-space-lg max-w-md space-y-space-lg">
            {description}
          </div>
        )}
        {action && <div className="mt-space-xl">{action}</div>}
      </div>
    </div>
  );
};
