import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Outlet} from '@tanstack/react-router';
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
  notFoundComponent: () => <ErrorState title="Page not found" showBackButton />,
});
