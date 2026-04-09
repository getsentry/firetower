import {useQuery} from '@tanstack/react-query';
import {Link, useRouterState} from '@tanstack/react-router';
import {Avatar} from 'components/Avatar';
import {cn} from 'utils/cn';

import {currentUserQueryOptions} from '../queries/currentUserQueryOptions';
import type {StatusFilterValue} from '../types';

const STORAGE_KEY = 'firetower_list_search';

const NAV_PAGES = [
  {label: 'Incidents', to: '/' as const},
  {label: 'Availability', to: '/availability' as const},
];

export const Header = () => {
  const routerState = useRouterState();
  const {data: currentUser} = useQuery(currentUserQueryOptions());
  const pathname = routerState.location.pathname;

  const isTopLevelRoute = NAV_PAGES.some(
    page => pathname === page.to || pathname === `${page.to}/`
  );

  const getPreservedSearch = (): {status?: StatusFilterValue[]} | undefined => {
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
    <header className="bg-background-primary border-secondary border-b">
      <div className="px-space-md py-space-md md:px-space-xl mx-auto max-w-6xl">
        {isTopLevelRoute ? (
          <div className="flex items-center justify-between">
            <nav className="gap-space-2xs flex">
              {NAV_PAGES.map(page => (
                <Link
                  key={page.to}
                  to={page.to}
                  preload="intent"
                  className={cn(
                    'rounded-radius-sm px-space-lg py-space-sm text-size-sm font-medium transition-colors',
                    {
                      'bg-background-secondary text-content-headings':
                        pathname === page.to || pathname === `${page.to}/`,
                      'text-content-secondary hover:text-content-headings':
                        pathname !== page.to && pathname !== `${page.to}/`,
                    }
                  )}
                >
                  {page.label}
                </Link>
              ))}
            </nav>
            <Link to="/" className="gap-space-sm flex items-center no-underline">
              <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
              <span className="text-content-headings text-xl font-semibold">
                Firetower
              </span>
            </Link>
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
              className="text-content-secondary hover:bg-background-secondary hover:text-content-accent px-space-md py-space-sm inline-flex items-center gap-2 rounded-sm text-xs transition-colors"
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
            {currentUser ? (
              <Avatar name={currentUser.name} src={currentUser.avatar_url} size="sm" />
            ) : (
              <div className="h-7 w-7" />
            )}
          </div>
        )}
      </div>
    </header>
  );
};
