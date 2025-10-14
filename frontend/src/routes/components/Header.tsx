import {Link, useRouterState} from '@tanstack/react-router';

import type {IncidentStatus} from '../queries/incidentsQueryOptions';

const STORAGE_KEY = 'firetower_list_search';

export const Header = () => {
  const routerState = useRouterState();

  // Check if we're on the root route
  const isRootRoute = routerState.location.pathname === '/';

  // Read from sessionStorage (synchronous, so no need for useEffect/useState)
  const getPreservedSearch = (): {status?: IncidentStatus[]} | undefined => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch {
        return undefined;
      }
    }
    return undefined;
  };

  const preservedSearch = getPreservedSearch();

  return (
    <nav className="bg-background-primary border-secondary border-b">
      <div className="px-space-md py-space-md md:px-space-xl mx-auto max-w-6xl">
        {isRootRoute ? (
          // Centered title on root route
          <div className="flex items-center justify-center">
            <Link to="/" className="gap-space-sm flex items-center no-underline">
              <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
              <span className="text-content-headings text-xl font-semibold">
                Firetower
              </span>
            </Link>
          </div>
        ) : (
          // Back button + centered title on other routes
          <div className="relative flex items-center justify-between">
            <Link
              to="/"
              search={preservedSearch}
              className="text-content-secondary hover:bg-background-secondary hover:text-accent px-space-md py-space-sm inline-flex items-center gap-2 rounded-sm text-xs transition-colors"
            >
              <span>←</span>
              <span>All Incidents</span>
            </Link>
            <Link
              to="/"
              className="gap-space-sm absolute left-1/2 flex -translate-x-1/2 items-center no-underline"
            >
              <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
              <span className="text-content-headings text-xl font-semibold">
                Firetower
              </span>
            </Link>
            {/* Spacer to balance layout */}
            <div className="w-24"></div>
          </div>
        )}
      </div>
    </nav>
  );
};
