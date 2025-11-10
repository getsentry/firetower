import type {ReactNode} from 'react';
import {Link} from '@tanstack/react-router';

interface ErrorStateProps {
  title?: string;
  description?: ReactNode;
  showBackButton?: boolean;
}

export const ErrorState = ({
  title = 'Something went wrong',
  description,
  showBackButton = false,
}: ErrorStateProps) => {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <div className="text-center">
        <h2 className="text-content-headings mb-space-lg text-2xl font-medium">
          {title}
        </h2>
        {description && (
          <div className="text-content-secondary mb-space-lg space-y-space-lg mx-auto max-w-md">
            {description}
          </div>
        )}
        {showBackButton && (
          <div className="mt-space-xl">
            <Link
              to="/"
              className="text-content-secondary hover:bg-background-secondary hover:text-content-accent px-space-md py-space-sm inline-flex items-center gap-2 rounded-sm transition-colors"
            >
              <span>{String.fromCharCode(8592)}</span>
              <span>All Incidents</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};
