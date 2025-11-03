import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Link, Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';
import {ErrorState} from 'components/ErrorState';

import {Header} from './components/Header';

const RootLayout = () => (
  <div className="bg-background-tertiary text-content-primary leading-default min-h-screen">
    <Header />
    <main className="px-space-md py-space-xl md:px-space-xl mx-auto max-w-6xl">
      <Outlet />
    </main>
    <TanStackRouterDevtools />
  </div>
);

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
  notFoundComponent: () => (
    <ErrorState
      title="Page not found"
      description="This page doesn't exist."
      action={
        <Link
          to="/"
          className="text-content-secondary hover:bg-background-secondary hover:text-content-accent px-space-md py-space-sm inline-flex items-center gap-2 rounded-sm transition-colors"
        >
          <span>{String.fromCharCode(8592)}</span>
          <span>All Incidents</span>
        </Link>
      }
    />
  ),
});
