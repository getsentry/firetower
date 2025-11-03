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
        <h2 className="text-content-headings mb-space-md text-2xl font-semibold">
          {title}
        </h2>
        {description && (
          <p className="text-content-secondary mx-auto mb-space-lg max-w-md">
            {description}
          </p>
        )}
        {action && <div className="mt-space-xl">{action}</div>}
      </div>
    </div>
  );
};
