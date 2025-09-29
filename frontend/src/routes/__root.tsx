import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';

import {Header} from './components/Header';

const RootLayout = () => (
  <div className="min-h-screen bg-background-tertiary text-content-primary leading-default">
    <Header />
    <main className="max-w-6xl mx-auto px-space-md py-space-xl md:px-space-xl">
      <Outlet />
    </main>
    <TanStackRouterDevtools />
  </div>
);

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
});
