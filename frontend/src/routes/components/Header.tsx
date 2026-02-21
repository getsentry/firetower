import {useQuery} from '@tanstack/react-query';
import {Link, useRouterState} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {cn} from 'utils/cn';

import {currentUserQueryOptions} from '../queries/currentUserQueryOptions';
import type {IncidentStatus} from '../queries/incidentsQueryOptions';

const STORAGE_KEY = 'firetower_list_search';

export const Header = () => {
  const routerState = useRouterState();
  const {data: currentUser} = useQuery(currentUserQueryOptions());

  const pathname = routerState.location.pathname;
  const isTopLevelRoute = pathname === '/' || pathname.startsWith('/availability');

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

  const navLinkClass = (isActive: boolean) =>
    cn(
      'rounded-radius-sm px-space-md py-space-sm text-size-sm font-medium transition-colors no-underline',
      {
        'bg-nav-active text-nav-primary': isActive,
        'text-nav-secondary hover:text-nav-primary': !isActive,
      }
    );

  return (
    <nav className="bg-nav border-b border-nav">
      <div className="px-space-md py-space-md md:px-space-xl mx-auto max-w-6xl">
        {isTopLevelRoute ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-space-md">
              <Link to="/" className="gap-space-sm flex items-center no-underline">
                <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
                <span className="text-nav-primary text-xl font-semibold">Firetower</span>
              </Link>
              <div className="gap-space-2xs flex items-center">
                <Link
                  to="/"
                  search={preservedSearch}
                  className={navLinkClass(pathname === '/')}
                >
                  Incidents
                </Link>
                <Link
                  to="/availability"
                  className={navLinkClass(pathname.startsWith('/availability'))}
                >
                  Availability
                </Link>
              </div>
            </div>
            {currentUser ? (
              <Avatar name={currentUser.name} src={currentUser.avatar_url} size="sm" />
            ) : (
              <div className="h-7 w-7" />
            )}
          </div>
        ) : (
          <div className="relative flex items-center justify-between">
            <Link
              to="/"
              search={preservedSearch}
              className="text-nav-secondary hover:text-nav-primary px-space-md py-space-sm inline-flex items-center gap-2 rounded-sm text-xs transition-colors"
            >
              <span>←</span>
              <span>All Incidents</span>
            </Link>
            <Link
              to="/"
              className="gap-space-sm absolute left-1/2 flex -translate-x-1/2 items-center no-underline"
            >
              <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
              <span className="text-nav-primary text-xl font-semibold">Firetower</span>
            </Link>
            {currentUser ? (
              <Avatar name={currentUser.name} src={currentUser.avatar_url} size="sm" />
            ) : (
              <div className="h-7 w-7" />
            )}
          </div>
        )}
      </div>
    </nav>
  );
};
