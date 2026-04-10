import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';
import {ErrorState} from 'components/ErrorState';
import {TooltipProvider} from 'components/Tooltip';

import {Header} from './components/Header';

const RootLayout = () => (
  <TooltipProvider delayDuration={200}>
    <div className="bg-background-tertiary text-content-primary leading-default min-h-screen">
      <Header />
      <main className="px-space-md py-space-xl md:px-space-xl mx-auto max-w-6xl">
        <Outlet />
      </main>
      <TanStackRouterDevtools />
    </div>
  </TooltipProvider>
);

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
  notFoundComponent: () => <ErrorState title="Page not found" showBackButton />,
});
