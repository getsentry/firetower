import type {QueryClient} from '@tanstack/react-query';
import {createRootRouteWithContext, Outlet} from '@tanstack/react-router';
import {TanStackRouterDevtools} from '@tanstack/react-router-devtools';

import {Header} from './components/Header';

const RootLayout = () => (
  <>
    <Header />
    <Outlet />
    <TanStackRouterDevtools />
  </>
);

export const Route = createRootRouteWithContext<{queryClient: QueryClient}>()({
  component: RootLayout,
});
